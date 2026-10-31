"""审阅修复的独立回归;真实副本经公开审计与文本 CLI 验证。"""

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts.verification_scope_audit import audit_baseline
from tests.a2_full_support import repository_copy
from tests.test_scope_baseline_audit import git

GROUPS_PATH = "scripts/verification_groups.py"


def test_required_flip_cannot_be_accepted_by_updating_central_sha(
    tmp_path: Path,
) -> None:
    root = repository_copy(tmp_path / "repo")
    git(root, "branch", "review-target")
    base = git(root, "rev-parse", "HEAD")
    declaration = root / GROUPS_PATH
    old_sha = hashlib.sha256(declaration.read_bytes()).hexdigest()
    declaration.write_text(
        declaration.read_text().replace(
            'Group("A1", ".a1.json", True,',
            'Group("A1", ".a1.json", False,',
            1,
        )
    )
    new_sha = hashlib.sha256(declaration.read_bytes()).hexdigest()
    central = root / "scripts/verification_scope_materials.py"
    assert central.read_text().count(old_sha) == 1
    central.write_text(central.read_text().replace(old_sha, new_sha))

    report = audit_baseline(root, base=base, integration_target="review-target")

    change = next(c for c in report["baseline"]["changes"] if c["path"] == GROUPS_PATH)
    assert change["category"] == "format_or_criteria"
    assert change["sensitivity"] == "sensitive"
    assert report["exit_code"] == 1
    assert not any(
        row["reason"] == "hash_drift" and row["path"] == GROUPS_PATH
        for row in report["files"]
    )
    assert {
        issue["group"]
        for issue in report["issues"]
        if issue["reason"] == "confirmation_required" and issue["path"] == GROUPS_PATH
    } == {"A1", "A2-01", "完整 A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10"}


@pytest.mark.parametrize(
    ("previous", "candidate"),
    [
        ('Group("A1",', 'Group("A1-renamed",'),
        ('".a1.json"', '".a1-renamed.json"'),
        ('"scripts.a1_acceptance:A1_GROUP"', '"scripts.a3_acceptance:write_group"'),
        ('"scripts.a1_scope"', "None"),
        ('"scripts.a1_scope")', '"scripts.a1_scope", ("A3",))'),
    ],
    ids=["name", "suffix", "writer", "receipt_scope", "dependencies"],
)
def test_production_declaration_semantic_fields_require_all_groups(
    tmp_path: Path, previous: str, candidate: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    git(root, "branch", "review-target")
    base = git(root, "rev-parse", "HEAD")
    declaration = root / GROUPS_PATH
    assert previous in declaration.read_text()
    declaration.write_text(declaration.read_text().replace(previous, candidate, 1))

    report = audit_baseline(root, base=base, integration_target="review-target")

    change = next(c for c in report["baseline"]["changes"] if c["path"] == GROUPS_PATH)
    assert change["category"] in ("format_or_criteria", "registration")
    assert change["sensitivity"] == "sensitive"
    assert len(change["affected_groups"]) >= 11
    assert {
        issue["group"]
        for issue in report["issues"]
        if issue["reason"] == "confirmation_required" and issue["path"] == GROUPS_PATH
    } == set(change["affected_groups"])


def test_production_group_helper_implementation_is_mechanical(tmp_path: Path) -> None:
    root = repository_copy(tmp_path / "repo")
    git(root, "branch", "review-target")
    base = git(root, "rev-parse", "HEAD")
    declaration = root / GROUPS_PATH
    declaration.write_text(
        declaration.read_text().replace(
            'names = "、".join(group.name for group in GROUPS)',
            'names = "、".join([group.name for group in GROUPS])',
        )
    )

    report = audit_baseline(root, base=base, integration_target="review-target")

    change = next(c for c in report["baseline"]["changes"] if c["path"] == GROUPS_PATH)
    assert change["category"] == "source_support"
    assert change["sensitivity"] == "mechanical"
    assert not any(
        issue["reason"] == "confirmation_required" and issue["path"] == GROUPS_PATH
        for issue in report["issues"]
    )


def test_text_cli_reports_downstream_review_and_actual_file_drift(
    tmp_path: Path,
) -> None:
    root = repository_copy(tmp_path / "repo")
    source = root / "scripts/verification_groups.py"
    source.write_text(source.read_text() + "\n# 普通维护\n")

    result = subprocess.run(
        [str(root / "scripts/audit-verification-scope")],
        capture_output=True,
        text=True,
        check=False,
        env={
            "UV_PROJECT_ENVIRONMENT": str(Path(__file__).resolve().parents[1] / ".venv")
        },
    )

    assert result.returncode == 1
    assert "需审阅/验证的受影响下游" in result.stdout
    assert "需重算下游登记" not in result.stdout
    assert "scripts/verification_groups.py: hash_drift" in result.stdout


def test_group_default_dependency_is_part_of_declaration_semantics(
    tmp_path: Path,
) -> None:
    root = repository_copy(tmp_path / "repo")
    git(root, "branch", "review-target")
    base = git(root, "rev-parse", "HEAD")
    declaration = root / GROUPS_PATH
    declaration.write_text(
        declaration.read_text().replace(
            "dependencies: tuple[str, ...] = ()",
            'dependencies: tuple[str, ...] = ("A3",)',
        )
    )

    report = audit_baseline(root, base=base, integration_target="review-target")

    change = next(c for c in report["baseline"]["changes"] if c["path"] == GROUPS_PATH)
    assert change["category"] == "format_or_criteria"
    assert change["sensitivity"] == "sensitive"
    assert len(change["affected_groups"]) == 11
    assert (
        sum(
            issue["reason"] == "confirmation_required" and issue["path"] == GROUPS_PATH
            for issue in report["issues"]
        )
        == 11
    )
