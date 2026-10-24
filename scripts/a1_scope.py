"""A1 已交付能力的固定离线测试范围。"""

from __future__ import annotations

# 测试语义变更时需审查对应能力, 并在同一次提交中更新哈希。
# 顺序用于机器结论; 缺失或字节漂移均不能宣称当前固定 A1 范围已通过。
REQUIRED_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_boundary_validation.py",
        "6326cc77cc74bd53077e5d4c1ce78f41355af4b5b5c2ebfd9c03907d9a9cfd7f",
    ),
    (
        "tests/test_value_prediction_validation.py",
        "e9bdc89448a22638f3632639f120bcf689a7f93c4d8e80279e2c73a5dafdc173",
    ),
    (
        "tests/test_reuse_assessment_validation.py",
        "eae721185b7a2405b422865feb4370f81bb2aa2608343be9f23f9e914d8bcc07",
    ),
    (
        "tests/test_decision_reason_validation.py",
        "2e0a578ec6daf5877dc64362c8b3a705733b8e742beedb1702488a02e2f0e19d",
    ),
    (
        "tests/test_contract_schema.py",
        "9471333e0ab7df64fa135b2587b289059ca935fd45b53e4cc81d173ab931eb9a",
    ),
    (
        "tests/test_contract_export.py",
        "49dca04977690856bb2e8a14b9acc063d54e3e26182174b6c2164ac7f0e41f9f",
    ),
    (
        "tests/test_contract_check.py",
        "35cb36600af73aca3bba4c52bcc2f83a92fe9f36f497f656a44c5394f6a962ae",
    ),
    (
        "tests/test_contract_cli.py",
        "84b86b8017b4cc94da95311409257fd1fc4ff575f840e3eef90c546893d59eaf",
    ),
    (
        "tests/test_cli_help.py",
        "c03c70471575a50a82ae68bca7fea6c5bf3f885921fbac626403f2ce133e4ff4",
    ),
    (
        "tests/test_screening_architecture.py",
        "459eab67c1077008eb5609f3f7dd21b73e7e8e6b32c9672c54ed3826c113834c",
    ),
    (
        "tests/test_offline_evidence.py",
        "843308e18b62b0115ba149fc8ad6db1db15a5d01679086e91802b5f153dc5d49",
    ),
    (
        "tests/test_a1_acceptance.py",
        "67907487c29bce8872f3855e15ed47bd9cc781257ba8c534e52dd8f8f35c6759",
    ),
)
