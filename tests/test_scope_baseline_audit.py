"""显式基线审计;合成 Git 仓库经公开 Python/CLI 接缝验证。"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import verification_scope_audit as audit

ROOT = Path(__file__).resolve().parents[1]
WRITERS = (("A", "scripts/sample_acceptance.py"),)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def repository(root: Path, *, drift: bool = False) -> str:
    (root / "scripts").mkdir()
    for name in (
        "__init__.py",
        "verification_scope_audit.py",
        "verification_scope_registry.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, root / "scripts" / name)
    (root / "docs/verification").mkdir(parents=True)
    (root / audit.CLASSIFICATION_PATH).write_text(
        json.dumps(
            {"classification_rules": {"live_documents": {"exact_paths": ["README.md"]}}}
        )
    )
    (root / "sample.py").write_text("value = 1\n")
    (root / "tests").mkdir()
    (root / "tests/test_sample.py").write_text("def test_sample():\n    assert True\n")
    sha = hashlib.sha256((root / "sample.py").read_bytes()).hexdigest()
    test_sha = hashlib.sha256((root / "tests/test_sample.py").read_bytes()).hexdigest()
    (root / "scripts/sample_scope.py").write_text(
        f'REQUIRED_SOURCE_MODULES = (("sample.py", "{sha}"),)\n'
        f'REQUIRED_TEST_MODULES = (("tests/test_sample.py", "{test_sha}"),)\n'
        'REQUIRED_TEST_CASE_COUNTS = {"tests/test_sample.py": 1}\n'
    )
    (root / "scripts/sample_acceptance.py").write_text(
        "from scripts.sample_scope import (REQUIRED_SOURCE_MODULES, "
        "REQUIRED_TEST_MODULES, REQUIRED_TEST_CASE_COUNTS)\n"
    )
    if drift:
        (root / "sample.py").write_text("value = 0\n")
    git(root, "init", "-b", "main")
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "base",
    )
    return git(root, "rev-parse", "HEAD")


def test_mechanical_candidate_is_read_only_and_reports_actual_baseline(
    tmp_path: Path,
) -> None:
    base = repository(tmp_path)
    (tmp_path / "sample.py").write_text("value = 2\n")
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }

    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )

    change = next(c for c in report["baseline"]["changes"] if c["path"] == "sample.py")
    assert change["origin"] == "current_change"
    assert change["sensitivity"] == "mechanical"
    assert change["groups"] == ["A"]
    assert change["affected_groups"] == ["A"]
    assert report["baseline"]["base"] == base
    assert report["baseline"]["target_commit"] == base
    assert report["exit_code"] == 1  # 候选不是登记写回。
    assert before == {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }


def confirmations_for(report: audit.AuditReport) -> list[dict[str, object]]:
    baseline = report["baseline"]
    return [
        {
            **{
                key: dict(baseline)[key]
                for key in (
                    "base",
                    "head",
                    "integration_target",
                    "target_commit",
                    "worktree_sha256",
                )
            },
            **{
                key: dict(change)[key]
                for key in (
                    "path",
                    "origin",
                    "category",
                    "old_sha256",
                    "new_sha256",
                    "old_entry_sha256",
                    "new_entry_sha256",
                )
            },
            "group": group,
            "reason": "逐项人工审阅测试断言，固定分母保持 1",
        }
        for change in baseline["changes"]
        if change["origin"] == "current_change" and change["sensitivity"] == "sensitive"
        for group in change["affected_groups"]
    ]


def test_sensitive_change_requires_exact_confirmation_and_dirty_identity(
    tmp_path: Path,
) -> None:
    base = repository(tmp_path)
    (tmp_path / "tests/test_sample.py").write_text(
        "def test_sample():\n    assert 1 == 1\n"
    )
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    assert [(i["group"], i["path"], i["reason"]) for i in report["issues"]] == [
        ("A", "tests/test_sample.py", "confirmation_required")
    ]
    confirmations = confirmations_for(report)
    confirmed = audit.audit_baseline(
        tmp_path,
        base=base,
        integration_target="main",
        writers=WRITERS,
        confirmations=confirmations,
    )
    assert confirmed["issues"] == []
    assert confirmed["baseline"]["changes"][0]["confirmed_groups"] == ["A"]
    (tmp_path / "unrelated.txt").write_text("dirty身份也包括未登记文件")
    stale = audit.audit_baseline(
        tmp_path,
        base=base,
        integration_target="main",
        writers=WRITERS,
        confirmations=confirmations,
    )
    assert {i["reason"] for i in stale["issues"]} == {
        "invalid_confirmation",
        "confirmation_required",
    }


def test_baseline_drift_survives_another_change_and_confirmation(
    tmp_path: Path,
) -> None:
    base = repository(tmp_path, drift=True)
    (tmp_path / "sample.py").write_text("value = 3\n")
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    changes = [c for c in report["baseline"]["changes"] if c["path"] == "sample.py"]
    assert [(c["origin"], c["sensitivity"]) for c in changes] == [
        ("baseline_drift", "mechanical"),
        ("current_change", "mechanical"),
    ]
    assert "baseline_drift" in {i["reason"] for i in report["issues"]}


def test_unbound_classification_control_requires_every_group(tmp_path: Path) -> None:
    base = repository(tmp_path)
    rules = tmp_path / audit.CLASSIFICATION_PATH
    value = json.loads(rules.read_text())
    value["classification_rules"]["live_documents"]["exact_paths"].append("new.md")
    rules.write_text(json.dumps(value))
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    change = report["baseline"]["changes"][0]
    assert (change["path"], change["category"], change["sensitivity"]) == (
        audit.CLASSIFICATION_PATH,
        "classification",
        "sensitive",
    )
    assert report["issues"][0]["reason"] == "confirmation_required"


def test_target_movement_and_nonancestor_are_rejected(tmp_path: Path) -> None:
    base = repository(tmp_path)
    (tmp_path / "sample.py").write_text("value = 4\n")
    git(tmp_path, "add", "sample.py")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "target moved",
    )
    mismatch = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    assert mismatch["issues"][-1]["reason"] == "baseline_target_mismatch"
    target = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "--detach", base)
    nonancestor = audit.audit_baseline(
        tmp_path, base=target, integration_target="main", writers=WRITERS
    )
    assert nonancestor["issues"][-1]["reason"] == "baseline_not_ancestor"


def test_cli_baseline_and_external_confirmation_are_read_only(tmp_path: Path) -> None:
    base = repository(tmp_path)
    for name in (
        "audit_verification_scope.py",
        "verification_scope_baseline.py",
        "verification_scope_collection.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, tmp_path / "scripts" / name)
    (tmp_path / "scripts/sample_acceptance.py").write_text(
        (tmp_path / "scripts/sample_acceptance.py").read_text()
        + "\ndef write():\n    pass\n"
    )
    (tmp_path / "scripts/a2_full_acceptance.py").write_text(
        "from types import SimpleNamespace\n"
        "from scripts.sample_acceptance import write\n"
        "def acceptance_groups():\n"
        "    return (SimpleNamespace(name='A', write=write),)\n"
    )
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "CLI registry",
    )
    base = git(tmp_path, "rev-parse", "HEAD")
    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            "-B",
            "-m",
            "scripts.audit_verification_scope",
            "--json",
            "--base",
            base,
            "--integration-target",
            "main",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["baseline"]["base"] == base
    test = tmp_path / "tests/test_sample.py"
    test.write_text("def test_sample():\n    assert 3 == 3\n")
    arguments = [
        str(ROOT / ".venv/bin/python"),
        "-B",
        "-m",
        "scripts.audit_verification_scope",
        "--json",
        "--base",
        base,
        "--integration-target",
        "main",
    ]
    missing = subprocess.run(arguments, cwd=tmp_path, capture_output=True, text=True)
    assert missing.returncode == 1
    external = tmp_path.with_suffix(".confirmations.json")
    external.write_text(json.dumps(confirmations_for(json.loads(missing.stdout))))
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    confirmed = subprocess.run(
        [*arguments, "--confirmations", str(external)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert confirmed.returncode == 1  # 确认不清除原登记的 hash_drift。
    assert json.loads(confirmed.stdout)["issues"] == []
    assert before == {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    internal = tmp_path / "confirmation-SECRET.json"
    internal.write_text("[]")
    rejected = subprocess.run(
        [*arguments, "--confirmations", str(internal)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 2
    assert "invalid_option_value" in rejected.stderr
    assert "SECRET" not in rejected.stderr


def test_source_hash_rebinding_is_mechanical_but_counts_are_sensitive(
    tmp_path: Path,
) -> None:
    base = repository(tmp_path)
    source = tmp_path / "sample.py"
    previous = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_text("value = 9\n")
    candidate = hashlib.sha256(source.read_bytes()).hexdigest()
    scope = tmp_path / "scripts/sample_scope.py"
    scope.write_text(scope.read_text().replace(previous, candidate))
    mechanical = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    assert {c["sensitivity"] for c in mechanical["baseline"]["changes"]} == {
        "mechanical"
    }
    assert mechanical["issues"] == []
    scope.write_text(
        scope.read_text().replace(
            '"tests/test_sample.py": 1', '"tests/test_sample.py": 2'
        )
    )
    sensitive = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    assert sensitive["issues"][-1]["reason"] == "confirmation_required"
    assert sensitive["issues"][-1]["path"] == "scripts/sample_scope.py"


@pytest.mark.parametrize(
    "field",
    [
        "base",
        "head",
        "integration_target",
        "target_commit",
        "worktree_sha256",
        "group",
        "path",
        "origin",
        "category",
        "old_sha256",
        "new_sha256",
        "old_entry_sha256",
        "new_entry_sha256",
        "reason",
    ],
)
def test_confirmation_cannot_be_reused_for_wrong_change(
    tmp_path: Path, field: str
) -> None:
    base = repository(tmp_path)
    (tmp_path / "tests/test_sample.py").write_text(
        "def test_sample():\n    assert 2 == 2\n"
    )
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    confirmations = confirmations_for(report)
    confirmations[0][field] = "" if field == "reason" else "wrong"
    result = audit.audit_baseline(
        tmp_path,
        base=base,
        integration_target="main",
        writers=WRITERS,
        confirmations=confirmations,
    )
    assert {i["reason"] for i in result["issues"]} == {
        "invalid_confirmation",
        "confirmation_required",
    }


def test_sensitive_change_requires_all_transitive_groups(tmp_path: Path) -> None:
    repository(tmp_path)
    scope = tmp_path / "scripts/sample_scope.py"
    sha = hashlib.sha256(scope.read_bytes()).hexdigest()
    test_sha = hashlib.sha256(
        (tmp_path / "tests/test_sample.py").read_bytes()
    ).hexdigest()
    (tmp_path / "scripts/downstream_scope.py").write_text(
        f'REQUIRED_SOURCE_MODULES = (("scripts/sample_scope.py", "{sha}"),)\n'
        f'REQUIRED_TEST_MODULES = (("tests/test_sample.py", "{test_sha}"),)\n'
        'REQUIRED_TEST_CASE_COUNTS = {"tests/test_sample.py": 1}\n'
    )
    (tmp_path / "scripts/downstream_acceptance.py").write_text(
        "from scripts.downstream_scope import (REQUIRED_SOURCE_MODULES, "
        "REQUIRED_TEST_MODULES, REQUIRED_TEST_CASE_COUNTS)\n"
    )
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "downstream",
    )
    base = git(tmp_path, "rev-parse", "HEAD")
    writers = (*WRITERS, ("B", "scripts/downstream_acceptance.py"))
    scope.write_text(
        scope.read_text().replace(
            '"tests/test_sample.py": 1', '"tests/test_sample.py": 2'
        )
    )
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=writers
    )
    change = next(
        c
        for c in report["baseline"]["changes"]
        if c["path"] == "scripts/sample_scope.py"
    )
    assert change["affected_groups"] == ["A", "B"]
    confirmations = [c for c in confirmations_for(report) if c["group"] == "A"]
    partial = audit.audit_baseline(
        tmp_path,
        base=base,
        integration_target="main",
        writers=writers,
        confirmations=confirmations,
    )
    assert ("B", "scripts/sample_scope.py", "confirmation_required") in [
        (i["group"], i["path"], i["reason"]) for i in partial["issues"]
    ]


def test_confirmed_restoration_does_not_erase_sensitive_baseline_drift(
    tmp_path: Path,
) -> None:
    repository(tmp_path)
    test = tmp_path / "tests/test_sample.py"
    original = test.read_bytes()
    test.write_text("def test_sample():\n    assert False\n")
    git(tmp_path, "add", "tests/test_sample.py")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "preexisting drift",
    )
    base = git(tmp_path, "rev-parse", "HEAD")
    test.write_bytes(original)
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    confirmed = audit.audit_baseline(
        tmp_path,
        base=base,
        integration_target="main",
        writers=WRITERS,
        confirmations=confirmations_for(report),
    )
    assert {f["reason"] for f in confirmed["files"]} == {"ok"}
    assert {i["reason"] for i in confirmed["issues"]} == {"baseline_drift"}
    assert confirmed["exit_code"] == 1
    assert [
        (c["origin"], c["sensitivity"]) for c in confirmed["baseline"]["changes"]
    ] == [("baseline_drift", "sensitive"), ("current_change", "sensitive")]


@pytest.mark.parametrize(
    "invalid", [None, {}, [None], [{"reason": "SECRET raw input"}]]
)
def test_invalid_confirmation_input_is_controlled(
    tmp_path: Path, invalid: object
) -> None:
    base = repository(tmp_path)
    report = audit.audit_baseline(
        tmp_path,
        base=base,
        integration_target="main",
        writers=WRITERS,
        confirmations=invalid,
    )
    assert "invalid_confirmation" in {i["reason"] for i in report["issues"]}
    assert "SECRET" not in str(report)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--base", "SECRET"],
        ["--integration-target", "SECRET"],
        ["--confirmations", "SECRET"],
        ["--base"],
        ["--integration-target"],
    ],
)
def test_cli_baseline_arguments_have_safe_chinese_guidance(
    arguments: list[str],
) -> None:
    result = subprocess.run(
        [str(ROOT / "scripts/audit-verification-scope"), *arguments],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "invalid_option_value" in result.stderr
    assert "--help" in result.stderr
    assert "SECRET" not in result.stderr


def test_baseline_reads_git_blob_bytes_without_archive_export_substitution(
    tmp_path: Path,
) -> None:
    repository(tmp_path)
    source = tmp_path / "sample.py"
    previous = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_text('value = "$Format:%H$"\n')
    candidate = hashlib.sha256(source.read_bytes()).hexdigest()
    scope = tmp_path / "scripts/sample_scope.py"
    scope.write_text(scope.read_text().replace(previous, candidate))
    (tmp_path / ".gitattributes").write_text("sample.py export-subst\n")
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "export attributes",
    )
    base = git(tmp_path, "rev-parse", "HEAD")
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=WRITERS
    )
    assert report["exit_code"] == 0, report["issues"]
    assert report["baseline"]["changes"] == []


def test_each_tree_uses_its_own_registry_and_src_package(tmp_path: Path) -> None:
    repository(tmp_path)
    (tmp_path / "src").mkdir()
    marker = tmp_path / "src/synthetic_domain.py"
    marker.write_text('GROUP = "A"\n')
    writer = tmp_path / "scripts/sample_acceptance.py"
    writer.write_text(writer.read_text() + "\ndef write():\n    pass\n")
    (tmp_path / "scripts/a2_full_acceptance.py").write_text(
        "from types import SimpleNamespace\n"
        "from scripts.sample_acceptance import write\n"
        "from synthetic_domain import GROUP\n"
        "def acceptance_groups():\n"
        "    return (SimpleNamespace(name=GROUP, write=write),)\n"
    )
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "src registry",
    )
    base = git(tmp_path, "rev-parse", "HEAD")
    marker.write_text('GROUP = "B"\n')
    report = audit.audit_baseline(tmp_path, base=base, integration_target="main")
    assert report["baseline"]["baseline_issues"] == []
    change = report["baseline"]["changes"][0]
    assert change["path"] == "scripts/sample_scope.py"
    assert change["old_sha256"] == change["new_sha256"]
    assert change["old_entry_sha256"] != change["new_entry_sha256"]
    assert change["affected_groups"] == ["A", "B"]
    assert change["category"] == "registration"
    assert {
        i["group"] for i in report["issues"] if i["reason"] == "confirmation_required"
    } == {"A", "B"}
