"""完整入口测试使用的独立 Git 工作树与进程边界。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def repository_copy(target: Path) -> Path:
    target.mkdir()
    paths = subprocess.run(
        ("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"),
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    for relative in set(paths.split(b"\0")) - {b""}:
        source = ROOT / os.fsdecode(relative)
        destination = target / os.fsdecode(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)
    subprocess.run(("git", "init", "-q", str(target)), check=True)
    subprocess.run(("git", "add", "."), cwd=target, check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ),
        cwd=target,
        check=True,
    )
    return target


def fake_checks(tmp_path: Path) -> tuple[Path, Path]:
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    environment = json.dumps(
        {
            "python": "3.14.0",
            "dependencies": dict.fromkeys(
                ("pydantic", "typer", "pytest", "ruff", "mypy"),
                "1.0",
            ),
        }
    )
    uv.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f'  *"python -c"*) printf "%s\\n" \'{environment}\' ;;\n'
        '  *) printf "%s\\n" "$*" >> "$A2_TEST_CHECK_LOG" ;;\n'
        "esac\n"
        'case "$*" in\n'
        '  *" pytest"*)\n'
        '    if [ "${A2_TEST_STOP:-}" = failed ]; then exit 1; fi\n'
        '    if [ "${A2_TEST_STOP:-}" = interrupted ]; then kill -TERM $$; fi ;;\n'
        "esac\nexit 0\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return binary, tmp_path / "checks.log"
