"""实际 wheel 安装后离开 Git/源码树执行创建与校验。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from tests.backup_support import populated


def test_installed_wheel_can_backup_without_git_or_an_editable_install(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheels"
    build = subprocess.run(
        [
            "uv",
            "build",
            "--offline",
            "--wheel",
            "--out-dir",
            str(wheel_dir),
        ],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    (wheel,) = wheel_dir.glob("*.whl")
    environment = tmp_path / "wheel-env"
    shutil.copytree(Path(sys.prefix), environment, symlinks=True)
    installed = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--offline",
            "--python",
            str(environment / "bin/python"),
            "--no-deps",
            str(wheel),
        ],
        env={**os.environ, "UV_CACHE_DIR": str(tmp_path / "cache")},
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    python = environment / "bin/python"
    identity = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import paper_radar,sys; print(paper_radar.__file__); print(sys.prefix)",
        ],
        cwd=isolated,
        capture_output=True,
        text=True,
    )
    assert identity.returncode == 0, identity.stderr
    assert str(environment) in identity.stdout
    assert str(repository) not in identity.stdout
    database, data_root, _ = populated(tmp_path / "materials")
    executable = environment / "bin/paper-radar"
    env = {
        "PATH": "/unavailable",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(repository / "tests/deny_network"),
    }
    created = subprocess.run(
        [
            str(executable),
            "backup",
            "create",
            "--database",
            str(database),
            "--data-root",
            str(data_root),
            "--output",
            str(tmp_path / "output"),
        ],
        cwd=isolated,
        env=env,
        text=True,
        capture_output=True,
    )
    assert created.returncode == 0, created.stderr
    (batch,) = (tmp_path / "output").iterdir()
    verified = subprocess.run(
        [str(executable), "backup", "verify", str(batch)],
        cwd=isolated,
        env=env,
        text=True,
        capture_output=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert (
        "SECRET"
        not in created.stdout + created.stderr + verified.stdout + verified.stderr
    )
