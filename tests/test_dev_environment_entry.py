"""在独立 checkout fixture 验证只读入口的解释器选择。"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    source = Path(__file__).resolve().parent.parent
    for name in (
        "__init__.py",
        "dev-environment",
        "dev_environment.py",
        "dev_environment_probes.py",
    ):
        shutil.copyfile(source / "scripts" / name, scripts / name)
    (root / ".python-version").write_text("3.14\n")
    return root


def _path(tmp_path: Path) -> Path:
    directory = tmp_path / "commands"
    directory.mkdir()
    dirname = shutil.which("dirname")
    assert dirname is not None
    (directory / "dirname").symlink_to(dirname)
    return directory


def _run(checkout: Path, commands: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(checkout / "scripts/dev-environment"), "--help"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PATH": str(commands)},
    )


@pytest.mark.parametrize("version", ["(3, 10, 0)", "(3, 11, 0)"])
def test_unsupported_host_python_has_controlled_chinese_error(
    checkout: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    commands = _path(tmp_path)
    driver = commands / "python3"
    code = f"import sys; sys.version_info={version}; exec(sys.argv[-1])"
    driver.write_text(
        f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -I -S -B -c "
        f'{shlex.quote(code)} "$@"\n'
    )
    driver.chmod(0o755)

    result = _run(checkout, commands)

    assert result.returncode == 1
    assert "Python >=3.12" in result.stderr
    assert "uv run --offline --locked" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_host_python_has_controlled_chinese_error(
    checkout: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    result = _run(checkout, _path(tmp_path))

    assert result.returncode == 1
    assert "Python >=3.12" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("absolute", [False, True])
def test_launcher_respects_custom_environment_with_spaces(
    checkout: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    absolute: bool,
) -> None:
    environment = checkout / "custom environment"
    (environment / "bin").mkdir(parents=True)
    (environment / "bin/python").symlink_to(sys.executable)
    monkeypatch.setenv(
        "UV_PROJECT_ENVIRONMENT",
        str(environment) if absolute else "custom environment",
    )

    result = _run(checkout, _path(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "只读检查" in result.stdout
    assert result.stderr == ""


def test_supported_host_python_can_show_help_without_project_environment(
    checkout: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    commands = _path(tmp_path)
    (commands / "python3").symlink_to(sys.executable)

    result = _run(checkout, commands)

    assert result.returncode == 0
    assert "只读检查" in result.stdout
    assert result.stderr == ""
