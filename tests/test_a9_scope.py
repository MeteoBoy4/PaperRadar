"""A9 固定实际实现但不自哈希;循环仍拒绝,scope 字节受运行身份保护。"""

from dataclasses import replace
from pathlib import Path

import pytest

from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_registry import load_scopes
from tests.a9_acceptance_support import ROOT, conclude, same_a9_run


def test_a9_scope_covers_actual_rules_support_and_omits_self_hash() -> None:
    from scripts.a9_scope import (
        REQUIRED_FIXTURE_FILES,
        REQUIRED_SOURCE_MODULES,
        REQUIRED_TEST_MODULES,
    )

    scopes = load_scopes(ROOT)
    scope = next(scope for scope in scopes if scope.group == "A9")
    assert not scope.errors
    # A9 自己的登记必须有效;其他 required 组的材料仍由其自身结论决定。
    report = audit_scopes(ROOT, (scope,))
    assert report["exit_code"] == 0, report["issues"]
    fixed = {
        path
        for path, _ in (
            *REQUIRED_SOURCE_MODULES,
            *REQUIRED_TEST_MODULES,
            *REQUIRED_FIXTURE_FILES,
        )
    }
    assert "scripts/a9_scope.py" not in fixed
    assert {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "src/paper_radar/reading").glob("*.py")
    } <= fixed
    assert {
        "scripts/a9_acceptance.py",
        "tests/test_screening_architecture.py",
        "tests/read_recovery_worker.py",
        "tests/fixtures/a9_coverage.json",
        "docs/contracts/read-validation.md",
        "docs/verification/contracts-read-validation-history.md",
        "contracts/read/read/v1/schema.json",
    } <= fixed


@pytest.mark.parametrize("self_reference", [True, False])
def test_a9_does_not_disable_scope_self_reference_or_cycle_rejection(
    self_reference: bool,
) -> None:
    scopes = load_scopes(ROOT)
    a9 = next(scope for scope in scopes if scope.group == "A9")
    a1 = next(scope for scope in scopes if scope.group == "A1")
    selected = a9 if self_reference else a1
    entries = selected.bindings.get("source", ())
    assert isinstance(entries, tuple)
    changed = replace(
        selected,
        bindings={**selected.bindings, "source": (*entries, (a9.path, "0" * 64))},
    )
    report = audit_scopes(
        ROOT,
        tuple(changed if scope.group == selected.group else scope for scope in scopes),
    )
    assert report["exit_code"] == 1
    assert report["order"] == []
    assert ("self_reference" if self_reference else "cycle") in {
        issue["reason"] for issue in report["issues"]
    }


def test_unhashed_a9_scope_bytes_still_change_the_bound_run_identity(
    tmp_path: Path,
) -> None:
    from tests.a2_full_support import repository_copy

    root = repository_copy(tmp_path / "repo")
    inputs = same_a9_run(tmp_path, root=root)
    scope = root / "scripts/a9_scope.py"
    scope.write_bytes(scope.read_bytes() + b"\n# changed scope identity\n")
    _, result = conclude(tmp_path, inputs, root=root)
    assert result["status"] == "failed"
    assert "identity_changed" in {reason["code"] for reason in result["reasons"]}
