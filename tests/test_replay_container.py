"""B-E16 独立 D1:来源封装保持标准恢复布局与严格成员集合。"""

import json
import subprocess
import sys
from pathlib import Path

from tests.exposure_support import backup, initialized


def test_restore_container_is_portable_and_keeps_standard_contents(
    tmp_path: Path,
) -> None:
    root = initialized(tmp_path / "demo")
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output
    (batch,) = (tmp_path / "backups").iterdir()
    target = tmp_path / "session"
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(target),
            "--replay-container",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.name for p in target.iterdir()} == {
        "contents",
        "views",
        "restore-receipt.json",
    }
    assert (target / "contents/database.sqlite3").read_bytes() == (
        batch / "database.sqlite3"
    ).read_bytes()
    receipt = json.loads((target / "restore-receipt.json").read_bytes())
    assert receipt["operation"] == "restore verify"
    assert receipt["batch_id"] == batch.name
    moved = target.with_name("moved")
    target.rename(moved)
    assert (moved / "contents/manifest.json").read_bytes() == (
        batch / "manifest.json"
    ).read_bytes()
