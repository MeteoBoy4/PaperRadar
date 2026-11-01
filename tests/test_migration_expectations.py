"""D1: 阻止当前迁移预期重新散落到测试与支撑文件。"""

from pathlib import Path

from tests.migration_expectations import EXPECTED_MIGRATION_REVISION


def test_current_migration_literal_has_single_owner() -> None:
    tests_root = Path(__file__).resolve().parent
    owners = sorted(
        path.relative_to(tests_root).as_posix()
        for path in tests_root.rglob("*.py")
        if "fixtures" not in path.relative_to(tests_root).parts[:-1]
        and EXPECTED_MIGRATION_REVISION in path.read_text(encoding="utf-8")
    )
    assert owners == ["migration_expectations.py"], owners
