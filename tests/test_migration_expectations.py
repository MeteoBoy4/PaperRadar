"""D1: 阻止当前迁移预期重新散落到测试与支撑文件。"""

from pathlib import Path

from tests.migration_expectations import EXPECTED_MIGRATION_REVISION


def test_current_migration_literal_has_single_owner() -> None:
    tests_root = Path(__file__).resolve().parent
    # 按 #139 检查源文本; 注释或更长字符串含有当前值也算重复。
    owners = sorted(
        path.relative_to(tests_root).as_posix()
        for path in tests_root.rglob("*.py")
        if path.relative_to(tests_root).parts[0] != "fixtures"
        and EXPECTED_MIGRATION_REVISION in path.read_text(encoding="utf-8")
    )
    assert owners == ["migration_expectations.py"], owners
