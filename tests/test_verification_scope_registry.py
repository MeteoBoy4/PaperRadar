"""writer 登记来源契约, 包含旧切片与 A3 汇总清单。"""

from pathlib import Path

import pytest

from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_registry import load_scopes

ROOT = Path(__file__).resolve().parents[1]


def test_real_registry_covers_all_writers_and_fixed_counts() -> None:
    scopes = load_scopes(ROOT)
    report = audit_scopes(ROOT, scopes)
    assert [s.path for s in scopes] == [
        "scripts/a1_scope.py",
        "scripts/a2_scope.py",
        "scripts/a2_full_scope.py",
        "scripts/a3_scope.py",
        "scripts/a4_scope.py",
        "scripts/a5_scope.py",
    ]
    assert report["exit_code"] == 0, report["issues"]
    # 一次性探针的 478 包括重复扫描的 A3 子清单; writer 消费汇总后为 419。
    assert len(report["files"]) == 419
    assert len({r["path"] for r in report["counts"]}) == 126
    assert (
        sum({r["path"]: r["expected_cases"] for r in report["counts"]}.values()) == 2519
    )
    assert "scripts/check-offline" in [
        f["path"] for f in report["files"] if f["group"] == "A2-01"
    ]


@pytest.mark.parametrize(
    "change", ["new", "renamed", "missing", "duplicate_count", "dynamic", "reassign"]
)
def test_writer_binding_changes_fail_closed(tmp_path: Path, change: str) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    writer = "from scripts.future_scope import REQUIRED_TEST_MODULES\n"
    scope = 'REQUIRED_TEST_MODULES = (("tests/a.py", "' + "0" * 64 + '"),)\n'
    if change == "new":
        writer += "from scripts.future_scope import EXTRA_FILES\n"
        scope += "EXTRA_FILES = REQUIRED_TEST_MODULES\n"
    elif change == "renamed":
        writer = writer.replace("REQUIRED_TEST_MODULES", "RENAMED_FILES")
        scope = scope.replace("REQUIRED_TEST_MODULES", "RENAMED_FILES")
    elif change == "missing":
        scope = ""
    elif change == "duplicate_count":
        writer += "from scripts.future_scope import REQUIRED_TEST_CASE_COUNTS\n"
        scope += 'REQUIRED_TEST_CASE_COUNTS = {"tests/a.py": 1, "tests/a.py": 2}\n'
    elif change == "dynamic":
        scope += "REQUIRED_TEST_MODULES += REQUIRED_TEST_MODULES\n"
    else:
        scope += "REQUIRED_TEST_MODULES = ()\n"
    (scripts / "future_acceptance.py").write_text(writer)
    (scripts / "future_scope.py").write_text(scope)

    scopes = load_scopes(tmp_path, writers=(("A6", "scripts/future_acceptance.py"),))
    report = audit_scopes(tmp_path, scopes)
    assert report["exit_code"] == 1
    expected = {
        "new": "unsupported_scope_constant",
        "renamed": "unsupported_writer_scope",
        "missing": "invalid_registration",
        "duplicate_count": "duplicate_count_key",
        "dynamic": "unsupported_registration",
        "reassign": "duplicate_registration",
    }
    assert expected[change] in [r["reason"] for r in report["issues"]]
