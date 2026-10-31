"""A1 已交付能力的固定离线测试范围。"""

from __future__ import annotations

from scripts.verification_scope_materials import SHARED_MATERIALS

# 测试语义变更时需审查对应能力, 并在同一次提交中更新哈希。
# 顺序用于机器结论; 缺失或字节漂移均不能宣称当前固定 A1 范围已通过。
REQUIRED_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_boundary_validation.py",
        SHARED_MATERIALS["tests/test_boundary_validation.py"],
    ),
    (
        "tests/test_value_prediction_validation.py",
        SHARED_MATERIALS["tests/test_value_prediction_validation.py"],
    ),
    (
        "tests/test_reuse_assessment_validation.py",
        SHARED_MATERIALS["tests/test_reuse_assessment_validation.py"],
    ),
    (
        "tests/test_decision_reason_validation.py",
        SHARED_MATERIALS["tests/test_decision_reason_validation.py"],
    ),
    (
        "tests/test_contract_schema.py",
        SHARED_MATERIALS["tests/test_contract_schema.py"],
    ),
    (
        "tests/test_contract_export.py",
        SHARED_MATERIALS["tests/test_contract_export.py"],
    ),
    ("tests/test_contract_check.py", SHARED_MATERIALS["tests/test_contract_check.py"]),
    ("tests/test_contract_cli.py", SHARED_MATERIALS["tests/test_contract_cli.py"]),
    ("tests/test_cli_help.py", SHARED_MATERIALS["tests/test_cli_help.py"]),
    (
        "tests/test_screening_architecture.py",
        SHARED_MATERIALS["tests/test_screening_architecture.py"],
    ),
    (
        "tests/test_offline_evidence.py",
        SHARED_MATERIALS["tests/test_offline_evidence.py"],
    ),
    ("tests/test_a1_acceptance.py", SHARED_MATERIALS["tests/test_a1_acceptance.py"]),
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = ()
