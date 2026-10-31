"""R4 公开帮助、legacy 声明与 A8 诊断回归;不增加历史固定分母。"""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verification_scope_audit import audit_baseline
from tests.a2_full_support import ROOT
from tests.scope_document_support import prepared_repository, writer_conclusion
from tests.test_scope_baseline_audit import WRITERS, git, repository


def help_copy(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    for name in ("check-offline", "verification_groups.py", "__init__.py"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    binary = tmp_path / "bin"
    binary.mkdir()
    for name in ("bash", "dirname"):
        source = shutil.which(name)
        assert source is not None
        (binary / name).symlink_to(source)
    return root, binary


def shell_help(
    root: Path, binary: Path, environment: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary / "bash"), str(root / "scripts/check-offline"), "--help"],
        cwd=root,
        env={
            **os.environ,
            "PATH": str(binary),
            "UV_PROJECT_ENVIRONMENT": environment,
            "LC_ALL": "C",
        },
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("mode", ["missing", "old_host", "invalid_project"])
def test_help_without_usable_python_has_chinese_recovery(
    tmp_path: Path, mode: str
) -> None:
    root, binary = help_copy(tmp_path)
    environment = "missing-environment"
    if mode != "missing":
        target = binary / "python3"
        if mode == "invalid_project":
            target = root / "custom/bin/python"
            target.parent.mkdir(parents=True)
            environment = "custom"
        target.write_text(
            "#!/bin/bash\n"
            'arguments=("$@")\n'
            'original_code="${arguments[-1]}"\n'
            "arguments[-1]='import sys; sys.version_info = (3, 11, 0); "
            "exec(sys.argv[1])'\n"
            f'exec {shlex.quote(sys.executable)} "${{arguments[@]}}" "$original_code"\n'
            if mode == "old_host"
            else "#!/bin/bash\nexit 1\n"
        )
        target.chmod(0o755)
    before = {p.relative_to(root) for p in root.rglob("*")}

    result = shell_help(root, binary, environment)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Python >=3.12" in result.stderr
    assert "无法" in result.stderr and "准备环境" in result.stderr
    assert "uv run --offline --locked" in result.stderr
    assert before == {p.relative_to(root) for p in root.rglob("*")}


@pytest.mark.parametrize("mode", ["host", "relative_project"])
def test_help_uses_host_or_relative_project_python_without_writes(
    tmp_path: Path, mode: str
) -> None:
    root, binary = help_copy(tmp_path)
    environment = "missing-environment"
    target = binary / "python3"
    if mode == "relative_project":
        target = root / "custom/bin/python"
        target.parent.mkdir(parents=True)
        environment = "custom"
    target.symlink_to(sys.executable)
    before = {p.relative_to(root) for p in root.rglob("*")}

    result = shell_help(root, binary, environment)

    assert result.returncode == 0, result.stderr
    assert "用法：./scripts/check-offline" in result.stdout
    assert "A2-01" in result.stdout and "A10" in result.stdout
    assert result.stderr == ""
    assert before == {p.relative_to(root) for p in root.rglob("*")}


def test_legacy_groups_agree_with_production_registration() -> None:
    from scripts.a1_acceptance import A1_GROUP
    from scripts.a2_acceptance import A2_01_GROUP
    from scripts.verification_groups import GROUPS

    by_name = {group.name: group for group in GROUPS}
    for legacy in (A1_GROUP, A2_01_GROUP):
        registered = by_name[legacy.name]
        assert (
            legacy.name,
            legacy.suffix,
            legacy.required,
            legacy.dependencies,
        ) == (
            registered.name,
            registered.suffix,
            registered.required,
            registered.dependencies,
        )


@pytest.mark.parametrize(
    ("relative", "name"),
    [
        ("scripts/a1_acceptance.py", "A1_GROUP"),
        ("scripts/a2_acceptance.py", "A2_01_GROUP"),
    ],
)
@pytest.mark.parametrize(
    ("previous", "candidate"),
    [
        ('name="old"', 'name="changed"'),
        ('suffix=".old.json"', 'suffix=".changed.json"'),
        ("required=True", "required=False"),
        ('dependencies=("A1",)', "dependencies=()"),
    ],
)
def test_legacy_declaration_change_remains_sensitive_after_rebinding(
    tmp_path: Path, relative: str, name: str, previous: str, candidate: str
) -> None:
    repository(tmp_path)
    source = tmp_path / relative
    source.write_text(
        f'{name} = AcceptanceGroup(name="old", suffix=".old.json", '
        'required=True, dependencies=("A1",))\n'
    )
    old_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    scope = tmp_path / "scripts/sample_scope.py"
    scope.write_text(
        scope.read_text().replace(
            "REQUIRED_SOURCE_MODULES = (",
            f'REQUIRED_SOURCE_MODULES = (("{relative}", "{old_sha}"), ',
        )
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
        "legacy declaration base",
    )
    git(tmp_path, "branch", "review-target")
    base = git(tmp_path, "rev-parse", "HEAD")
    source.write_text(source.read_text().replace(previous, candidate))
    new_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    scope.write_text(scope.read_text().replace(old_sha, new_sha))

    report = audit_baseline(
        tmp_path, base=base, integration_target="review-target", writers=WRITERS
    )

    change = next(c for c in report["baseline"]["changes"] if c["path"] == relative)
    assert change["category"] == "format_or_criteria"
    assert change["sensitivity"] == "sensitive"
    assert change["origin"] == "current_change"
    assert not [f for f in report["files"] if f["reason"] == "hash_drift"]
    assert {
        issue["group"]
        for issue in report["issues"]
        if issue["reason"] == "confirmation_required" and issue["path"] == relative
    } == {"A"}


def test_a8_scope_audit_failure_has_controlled_diagnostic_item(tmp_path: Path) -> None:
    root = prepared_repository(
        tmp_path / "repo", reviewed=frozenset(), verified_groups=frozenset({"A8"})
    )
    scope = root / "scripts/a8_scope.py"
    scope.write_text(
        scope.read_text().replace('"scripts/a7_scope.py",', '"scripts/a8_scope.py",')
    )

    result = writer_conclusion(root, tmp_path / "output", 8)

    assert result["status"] == "failed"
    assert any(reason["code"] == "scope_drift" for reason in result["reasons"])
    assert any(
        reason["code"] == "scope_drift"
        and reason.get("item") == "scope_references.self_reference"
        for reason in result["reasons"]
    )
    assert "Traceback" not in json.dumps(result)
