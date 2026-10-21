"""writer 登记来源契约, 包含旧切片与 A3 汇总清单。"""

import importlib
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_registry import load_scopes

ROOT = Path(__file__).resolve().parents[1]


def test_real_registry_covers_all_writers_and_fixed_counts() -> None:
    scopes = load_scopes(ROOT)
    report = audit_scopes(ROOT, scopes)
    groups = acceptance_groups()
    assert [scope.group for scope in scopes] == [group.name for group in groups]
    assert report["exit_code"] == 0, report["issues"]
    # 与 writer 实际导入的权威常量逐项比对, 不再维护第二套固定总数。
    for group in groups:
        writer = importlib.import_module(group.write.__module__)
        for kind, constant in (
            ("test", "REQUIRED_TEST_MODULES"),
            ("source", "REQUIRED_SOURCE_MODULES"),
            ("fixture", "REQUIRED_FIXTURE_FILES"),
        ):
            expected_files = getattr(writer, constant, ())
            if kind == "test":
                expected_files = (
                    *expected_files,
                    *getattr(writer, "A1_TEST_MODULES", ()),
                )
            actual = [
                (r["path"], r["expected_sha256"])
                for r in report["files"]
                if r["group"] == group.name and r["kind"] == kind
            ]
            assert sorted(actual) == sorted(expected_files)
        expected_counts = getattr(writer, "REQUIRED_TEST_CASE_COUNTS", {})
        assert {
            r["path"]: r["expected_cases"]
            for r in report["counts"]
            if r["group"] == group.name
        } == expected_counts
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


@pytest.mark.parametrize("import_style", ["constant", "module"])
def test_additional_scope_cannot_hide_unchecked_bindings(
    tmp_path: Path,
    import_style: str,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (tmp_path / "test_one.py").write_bytes(b"")
    digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    writer = "from scripts.primary_scope import REQUIRED_TEST_MODULES\n"
    if import_style == "constant":
        writer += "from scripts.extra_scope import REQUIRED_SOURCE_MODULES\n"
    else:
        writer += (
            "from scripts import extra_scope\n"
            "value = extra_scope.REQUIRED_SOURCE_MODULES\n"
        )
    (scripts / "future_acceptance.py").write_text(writer)
    (scripts / "primary_scope.py").write_text(
        f"REQUIRED_TEST_MODULES = (('test_one.py', '{digest}'),)\n"
    )
    (scripts / "extra_scope.py").write_text(
        f"REQUIRED_SOURCE_MODULES = (('missing_source.py', '{digest}'),)\n"
    )
    report = audit_scopes(
        tmp_path,
        load_scopes(
            tmp_path,
            writers=(("A6", "scripts/future_acceptance.py"),),
        ),
    )
    assert report["exit_code"] == 1
    assert report["issues"]


def test_secondary_test_imports_are_also_hashed(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (tmp_path / "test_one.py").write_bytes(b"")
    digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    (scripts / "future_acceptance.py").write_text(
        "from scripts.primary_scope import REQUIRED_TEST_MODULES\n"
        "from scripts.extra_scope import REQUIRED_TEST_MODULES as EXTRA_TESTS\n"
    )
    for scope, test in (("primary", "test_one.py"), ("extra", "missing_test.py")):
        (scripts / f"{scope}_scope.py").write_text(
            f"REQUIRED_TEST_MODULES = (('{test}', '{digest}'),)\n"
        )
    report = audit_scopes(
        tmp_path,
        load_scopes(
            tmp_path,
            writers=(("A6", "scripts/future_acceptance.py"),),
        ),
    )
    assert report["exit_code"] == 1
    assert report["files"][-1]["path"] == "missing_test.py"
    assert report["files"][-1]["reason"] == "missing_file"
