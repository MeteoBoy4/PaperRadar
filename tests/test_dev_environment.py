"""开发环境检查的公开行为; 系统探测在 I/O 边界替换。"""

import getpass
import json
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import NoReturn

import pytest

from scripts.dev_environment import check_environment
from scripts.dev_environment_probes import Capacity, Probes, Quota, git_isolated

GIB = 1024**3
HEALTHY = Probes(
    capacity=lambda path: Capacity(9 * GIB, 100_000),
    quota=lambda path: Quota(8 * GIB, 2 * GIB),
    git_isolated=lambda path: True,
    writable=lambda path: True,
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".python-version").write_text("3.14\n")
    environment = project / ".venv"
    environment.mkdir()
    (environment / "pyvenv.cfg").write_text("version_info = 3.14.4\n")
    _python(environment, "3.14.4")
    return project


def _python(environment: Path, version: str) -> None:
    executable = environment / "bin/python"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(version)}\n")
    executable.chmod(0o755)


def test_healthy_environment_reports_capacity_without_changing_files(
    tmp_path: Path,
    project: Path,
) -> None:
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    probes = Probes(
        capacity=lambda path: Capacity(9 * GIB, 100_000),
        quota=lambda path: Quota(8 * GIB, 2 * GIB),
        git_isolated=lambda path: True,
        writable=lambda path: True,
    )

    report = check_environment(project, temporary, probes=probes)

    assert report.exit_code == 0
    assert report.checks["capacity"].reason == "ok"
    assert report.checks["capacity"].facts["effective_available_bytes"] == 6 * GIB
    assert report.checks["interpreter"].facts["actual"] == "3.14.4"
    assert list(temporary.iterdir()) == []


@pytest.mark.parametrize(
    ("filesystem_gib", "quota", "expected_bytes", "reason"),
    [
        (9, Quota(6 * GIB, 2 * GIB), 4 * GIB, "space_insufficient"),
        (4, Quota(9 * GIB, GIB), 4 * GIB, "space_insufficient"),
        (5, Quota(9 * GIB, GIB), 5 * GIB, "space_insufficient"),
        (9, Quota(9 * GIB, 10 * GIB), 0, "space_insufficient"),
        (9, None, None, "quota_unknown"),
    ],
)
def test_capacity_requires_known_quota_and_more_than_five_gib(
    tmp_path: Path,
    project: Path,
    filesystem_gib: int,
    quota: Quota | None,
    expected_bytes: int | None,
    reason: str,
) -> None:
    probes = Probes(
        capacity=lambda path: Capacity(filesystem_gib * GIB, 100_000),
        quota=lambda path: quota,
        git_isolated=lambda path: True,
        writable=lambda path: True,
    )

    report = check_environment(project, tmp_path, probes=probes)

    assert report.exit_code == 1
    check = report.checks["capacity"]
    assert check.reason == reason
    assert check.facts["effective_available_bytes"] == expected_bytes
    assert check.facts["statvfs_available_bytes"] == filesystem_gib * GIB


@pytest.mark.parametrize(
    ("probes", "name", "reason"),
    [
        (replace(HEALTHY, writable=lambda path: False), "temporary", "not_writable"),
        (replace(HEALTHY, git_isolated=lambda path: False), "git", "git_not_isolated"),
        (
            replace(HEALTHY, capacity=lambda path: Capacity(9 * GIB, 0)),
            "inodes",
            "inodes_insufficient",
        ),
    ],
)
def test_failed_environment_checks_are_reported(
    tmp_path: Path,
    project: Path,
    probes: Probes,
    name: str,
    reason: str,
) -> None:
    report = check_environment(project, tmp_path, probes=probes)

    assert report.exit_code == 1
    assert report.checks[name].reason == reason


def test_real_git_probe_rejects_symlink_into_worktree_with_spaces(
    tmp_path: Path,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = tmp_path / "work tree"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    link = tmp_path / "link"
    link.symlink_to(worktree, target_is_directory=True)
    # Git 的环境覆盖不能把仓库内的目录伪装成已隔离。
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(worktree.parent))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nonexistent"))

    report = check_environment(
        project,
        link,
        probes=replace(HEALTHY, git_isolated=git_isolated),
    )

    assert report.checks["git"].reason == "git_not_isolated"
    assert report.checks["temporary"].facts["path"] == str(worktree.resolve())
    assert report.exit_code == 1


def test_real_git_probe_accepts_directory_outside_any_worktree(tmp_path: Path) -> None:
    assert git_isolated(tmp_path)


def test_residue_is_reported_with_quoted_manual_cleanup_and_never_removed(
    tmp_path: Path,
    project: Path,
) -> None:
    root = tmp_path / "temporary with spaces"
    residue = root / f"pytest-of-{getpass.getuser()}"
    residue.mkdir(parents=True)
    old = residue / "garbage-one"
    old.mkdir()
    content = old / "fixture"
    content.write_bytes(b"keep this")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "unrelated").write_bytes(b"x" * 100_000)
    (old / "external").symlink_to(outside, target_is_directory=True)
    old.chmod(0o555)

    report = check_environment(project, root, probes=HEALTHY)

    assert report.exit_code == 0
    check = report.checks["residue"]
    assert check.reason == "residue_present"
    assert isinstance(check.facts["allocated_bytes"], int)
    assert check.facts["allocated_bytes"] < 100_000
    assert check.facts["cleanup_command"] == (
        f"chmod -R u+w '{residue}' && rm -rf -- '{residue}'"
    )
    assert content.read_bytes() == b"keep this"
    assert old.stat().st_mode & 0o777 == 0o555


@pytest.mark.parametrize(
    ("version", "reason"),
    [("3.12.14", "python_mismatch"), ("3.14.4", "ok"), ("malformed", "python_unknown")],
)
def test_project_interpreter_version_is_checked(
    tmp_path: Path,
    project: Path,
    version: str,
    reason: str,
) -> None:
    _python(project / ".venv", version)

    report = check_environment(project, tmp_path, probes=HEALTHY)

    assert report.checks["interpreter"].reason == reason


def test_missing_project_environment_has_actionable_failure(tmp_path: Path) -> None:
    report = check_environment(tmp_path, tmp_path, probes=HEALTHY)

    assert report.exit_code == 1
    assert report.checks["interpreter"].reason == "python_unknown"


@pytest.mark.parametrize("boundary", ["capacity", "quota", "git_isolated"])
def test_probe_errors_are_controlled_and_do_not_disclose_exception(
    tmp_path: Path,
    project: Path,
    boundary: str,
) -> None:
    def unavailable(path: Path) -> NoReturn:
        raise OSError("synthetic-secret")

    if boundary == "capacity":
        probes = replace(HEALTHY, capacity=unavailable)
        name, reason = "capacity", "capacity_unknown"
    elif boundary == "quota":
        probes = replace(HEALTHY, quota=unavailable)
        name, reason = "capacity", "quota_unknown"
    else:
        probes = replace(HEALTHY, git_isolated=unavailable)
        name, reason = "git", "git_unknown"

    report = check_environment(project, tmp_path, probes=probes)

    assert report.exit_code == 1
    assert report.checks[name].reason == reason
    assert "synthetic-secret" not in str(report)


@pytest.mark.parametrize("quota_known", [True, False])
def test_cli_json_and_chinese_text_express_the_same_facts(
    tmp_path: Path,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    quota_known: bool,
) -> None:
    from scripts.dev_environment import main

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    probes = HEALTHY if quota_known else replace(HEALTHY, quota=lambda path: None)
    expected_exit = 0 if quota_known else 1
    assert main(["check", "--json"], project=project, probes=probes) == expected_exit
    payload = json.loads(capsys.readouterr().out)
    assert main(["check"], project=project, probes=probes) == expected_exit
    text = capsys.readouterr().out

    assert payload["exit_code"] == expected_exit
    for item in payload["checks"].values():
        assert item["reason"] in text
        assert item["help_zh"] in text
        assert json.dumps(item["facts"], ensure_ascii=False, sort_keys=True) in text


def test_actual_entry_help_and_invalid_arguments_are_local_and_controlled() -> None:
    root = Path(__file__).resolve().parent.parent
    for arguments, expected in [
        (["--help"], 0),
        (["check", "--help"], 0),
        (["prepare"], 2),
    ]:
        result = subprocess.run(
            [str(root / "scripts/dev-environment"), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == expected
        assert "Traceback" not in result.stderr
        assert "联网" in result.stdout or "参数错误" in result.stderr


@pytest.mark.parametrize(
    ("arguments", "explanation"),
    [
        ([], "缺少 check 子命令"),
        (["prepare"], "仅支持 check 子命令"),
        (["check", "--synthetic-secret"], "未知选项或多余参数"),
    ],
)
def test_argument_errors_explain_controlled_causes(
    arguments: list[str],
    explanation: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts.dev_environment import main

    with pytest.raises(SystemExit) as caught:
        main(arguments)

    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert explanation in error
    assert "--help" in error
    assert "synthetic-secret" not in error


def test_explicit_project_environment_override_is_checked(
    tmp_path: Path,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = project / "custom environment"
    environment.mkdir()
    (environment / "pyvenv.cfg").write_text("version_info = 3.12.14\n")
    _python(environment, "3.12.14")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "custom environment")

    report = check_environment(project, tmp_path, probes=HEALTHY)

    assert report.checks["interpreter"].reason == "python_mismatch"
    assert report.checks["interpreter"].facts["path"] == str(environment)


def test_missing_interpreter_cannot_pass_using_stale_configuration(
    tmp_path: Path,
    project: Path,
) -> None:
    (project / ".venv/bin/python").unlink()
    report = check_environment(project, tmp_path, probes=HEALTHY)
    assert report.checks["interpreter"].reason == "python_unknown"


def test_actual_interpreter_version_takes_precedence_over_stale_configuration(
    tmp_path: Path,
    project: Path,
) -> None:
    executable = project / ".venv/bin/python"
    executable.unlink()
    executable.symlink_to(sys.executable)
    (project / ".venv/pyvenv.cfg").write_text("version_info = 0.0.0\n")
    (project / ".python-version").write_text(
        f"{sys.version_info.major}.{sys.version_info.minor}\n"
    )

    report = check_environment(project, tmp_path, probes=HEALTHY)

    assert report.checks["interpreter"].reason == "ok"
    assert report.checks["interpreter"].facts["actual"] != "0.0.0"


def test_pytest_residue_uses_the_same_user_resolution_as_pytest(
    tmp_path: Path,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGNAME", "synthetic-pytest-user")
    residue = tmp_path / "pytest-of-synthetic-pytest-user"
    residue.mkdir()
    (residue / "old").write_bytes(b"fixture")

    report = check_environment(project, tmp_path, probes=HEALTHY)

    assert report.checks["residue"].reason == "residue_present"
    assert report.checks["residue"].facts["path"] == str(residue)


def test_command_works_with_file_mutations_denied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    root = Path(__file__).resolve().parent.parent
    config_before = (root / ".venv/pyvenv.cfg").read_bytes()
    code = """
import os, sys
def deny(event, args):
    if event == 'open':
        flags = args[2]
        writes = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        if isinstance(flags, int) and flags & writes:
            raise AssertionError('write forbidden')
    mutations = {'os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.chmod',
                 'os.link', 'os.symlink'}
    if event in mutations:
        raise AssertionError('mutation forbidden')
sys.addaudithook(deny)
from scripts.dev_environment import main
raise SystemExit(main(['check', '--json']))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode in {0, 1}, result.stderr
    assert json.loads(result.stdout)["exit_code"] == result.returncode
    assert result.stderr == ""
    assert list(tmp_path.iterdir()) == []
    assert (root / ".venv/pyvenv.cfg").read_bytes() == config_before


def test_missing_temporary_root_and_residue_symlink_fail_safely(
    tmp_path: Path,
    project: Path,
) -> None:
    report = check_environment(project, tmp_path / "absent", probes=HEALTHY)
    assert report.exit_code == 1
    assert report.checks["temporary"].reason == "temporary_unknown"

    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "temporary"
    root.mkdir()
    residue = root / f"pytest-of-{getpass.getuser()}"
    residue.symlink_to(outside, target_is_directory=True)
    report = check_environment(project, root, probes=HEALTHY)
    assert report.exit_code == 1
    assert report.checks["residue"].reason == "residue_unknown"
    assert "cleanup_command" not in report.checks["residue"].facts
