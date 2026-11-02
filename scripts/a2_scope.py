"""Issue #16 的固定 A2-01 离线验收范围。"""

from __future__ import annotations

from scripts.verification_scope_materials import SHARED_MATERIALS

SCOPE = "a2_01_profile_runtime_config_snapshots"
ISSUE = 16
SNAPSHOT_FORMAT_VERSION = 1
MIGRATION_REVISION = "feed07_parser_versions"

# 材料组装重构只更新 service 并登记 material_assembly, 原固定测试不变。
# 哈希在完成本票改动后固定。预期值不能从被检查文件动态生成。
# #27 复核快照发现与前缀 CLI 接入后的源码绑定。
# scope、A2-01 固定测试及其历史未覆盖范围保持不变。完整 A2 结论归 #25。
# #24 复核固定锁等待、受控忙错误与 compile 恢复帮助后的源码绑定。
REQUIRED_TEST_MODULES: tuple[tuple[str, str], ...] = (
    ("tests/test_config_service.py", SHARED_MATERIALS["tests/test_config_service.py"]),
    (
        "tests/test_config_validation.py",
        SHARED_MATERIALS["tests/test_config_validation.py"],
    ),
    ("tests/test_config_cli.py", SHARED_MATERIALS["tests/test_config_cli.py"]),
    (
        "tests/test_config_architecture.py",
        SHARED_MATERIALS["tests/test_config_architecture.py"],
    ),
    ("tests/test_a2_acceptance.py", SHARED_MATERIALS["tests/test_a2_acceptance.py"]),
)

REQUIRED_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/migration_expectations.py",
        SHARED_MATERIALS["tests/migration_expectations.py"],
    ),
    (
        "scripts/verification_groups.py",
        SHARED_MATERIALS["scripts/verification_groups.py"],
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
    ("src/paper_radar/cli.py", SHARED_MATERIALS["src/paper_radar/cli.py"]),
    (
        "src/paper_radar/config/__init__.py",
        SHARED_MATERIALS["src/paper_radar/config/__init__.py"],
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
        "src/paper_radar/config/escalation.py",
        SHARED_MATERIALS["src/paper_radar/config/escalation.py"],
    ),
    (
        "src/paper_radar/config/errors.py",
        SHARED_MATERIALS["src/paper_radar/config/errors.py"],
    ),
    (
        "src/paper_radar/config/identity.py",
        SHARED_MATERIALS["src/paper_radar/config/identity.py"],
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
        "src/paper_radar/config/topics.py",
        SHARED_MATERIALS["src/paper_radar/config/topics.py"],
    ),
    (
        "src/paper_radar/config/yaml_loader.py",
        SHARED_MATERIALS["src/paper_radar/config/yaml_loader.py"],
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
        "tests/config_reuse_support.py",
        SHARED_MATERIALS["tests/config_reuse_support.py"],
    ),
    ("tests/config_test_support.py", SHARED_MATERIALS["tests/config_test_support.py"]),
    (
        "tests/deny_network/sitecustomize.py",
        SHARED_MATERIALS["tests/deny_network/sitecustomize.py"],
    ),
    ("scripts/check-offline", SHARED_MATERIALS["scripts/check-offline"]),
    ("scripts/a2_acceptance.py", SHARED_MATERIALS["scripts/a2_acceptance.py"]),
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
        "tests/config_extraction_support.py",
        SHARED_MATERIALS["tests/config_extraction_support.py"],
    ),
    (
        "src/paper_radar/config/adapters.py",
        SHARED_MATERIALS["src/paper_radar/config/adapters.py"],
    ),
    (
        "src/paper_radar/config/adapter_loading.py",
        SHARED_MATERIALS["src/paper_radar/config/adapter_loading.py"],
    ),
    (
        "tests/config_adapter_support.py",
        SHARED_MATERIALS["tests/config_adapter_support.py"],
    ),
    (
        "src/paper_radar/config/read.py",
        SHARED_MATERIALS["src/paper_radar/config/read.py"],
    ),
    ("tests/config_read_support.py", SHARED_MATERIALS["tests/config_read_support.py"]),
    (
        "src/paper_radar/config/journals.py",
        SHARED_MATERIALS["src/paper_radar/config/journals.py"],
    ),
    (
        "tests/config_journals_support.py",
        SHARED_MATERIALS["tests/config_journals_support.py"],
    ),
    (
        "src/paper_radar/config/projections.py",
        SHARED_MATERIALS["src/paper_radar/config/projections.py"],
    ),
    (
        "src/paper_radar/config/diff.py",
        SHARED_MATERIALS["src/paper_radar/config/diff.py"],
    ),
    (
        "tests/config_projection_support.py",
        SHARED_MATERIALS["tests/config_projection_support.py"],
    ),
    # #27 新实现与测试文件仅绑定字节。不扩展上方 A2-01 固定测试验收范围。
    (
        "src/paper_radar/config/material_names.py",
        SHARED_MATERIALS["src/paper_radar/config/material_names.py"],
    ),
    (
        "src/paper_radar/config/snapshot_queries.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_queries.py"],
    ),
    (
        "src/paper_radar/config/snapshot_cli.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_cli.py"],
    ),
    (
        "src/paper_radar/config/snapshot_summary.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_summary.py"],
    ),
    (
        "src/paper_radar/storage/snapshot_queries.py",
        SHARED_MATERIALS["src/paper_radar/storage/snapshot_queries.py"],
    ),
    (
        "tests/test_config_snapshot_queries.py",
        SHARED_MATERIALS["tests/test_config_snapshot_queries.py"],
    ),
    (
        "tests/test_config_snapshot_cli.py",
        SHARED_MATERIALS["tests/test_config_snapshot_cli.py"],
    ),
    (
        "tests/test_config_snapshot_architecture.py",
        SHARED_MATERIALS["tests/test_config_snapshot_architecture.py"],
    ),
    (
        "tests/config_snapshot_support.py",
        SHARED_MATERIALS["tests/config_snapshot_support.py"],
    ),
)

REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML")

NOT_IMPLEMENTED = (
    "read_output_contract",
    "read_execution",
    "body_extraction_execution",
    "stage_config_projections",
    "calibration_baseline",
    "config_diff",
    "stage_input_fingerprints",
    "automatic_fulltext_reading",
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = ()
