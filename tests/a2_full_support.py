"""完整入口测试使用的独立 Git 工作树与进程边界。"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def passed_receipt(run_id: str) -> dict[str, object]:
    from scripts.a2_full_scope import (
        RECEIPT_COUNTERS,
        REQUIRED_TEST_CASE_COUNTS,
        ReceiptCounter,
    )

    return {
        "format_version": 1,
        "run_id": run_id,
        "completed": True,
        "exit_code": 0,
        "modules": {
            name: {
                key.value: count
                if key in (ReceiptCounter.COLLECTED, ReceiptCounter.PASSED)
                else 0
                for key in RECEIPT_COUNTERS
            }
            for name, count in REQUIRED_TEST_CASE_COUNTS.items()
        },
    }


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
    init_fixture_repository(target)
    return target


def init_fixture_repository(path: Path) -> None:
    subprocess.run(("git", "init", "-q", str(path)), check=True)
    subprocess.run(("git", "add", "."), cwd=path, check=True)
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
        cwd=path,
        check=True,
    )


def fake_checks(tmp_path: Path) -> tuple[Path, Path]:
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    writer = tmp_path / "write_receipt.py"
    writer.write_text(
        "import json, os\nfrom pathlib import Path\n"
        f"payload = {passed_receipt('fixture')!r}\n"
        'payload["run_id"] = os.environ["PAPER_RADAR_TEST_RUN_ID"]\n'
        'Path(os.environ["PAPER_RADAR_TEST_RECEIPT"]).write_text(json.dumps(payload))\n',
        encoding="utf-8",
    )
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
        '    if [ "${A2_TEST_STOP:-}" = interrupted ]; then kill -TERM $$; fi\n'
        f"    {shlex.quote(sys.executable)} {shlex.quote(str(writer))} ;;\n"
        "esac\nexit 0\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return binary, tmp_path / "checks.log"
