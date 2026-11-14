"""回放合成材料与真实产品子进程;不使用现场材料。"""

import subprocess
import sys
from pathlib import Path

from tests.exposure_support import backup, initialized


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(Path(sys.executable).with_name("paper-radar")), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )


def restored_demo(tmp_path: Path) -> tuple[Path, tuple[Path, ...]]:
    root = initialized(tmp_path / "demo-experiment")
    for name in ("config", "pi-materials", "pi-install", "models"):
        path = root.root / name
        path.mkdir(exist_ok=True)
        (path / "synthetic.txt").write_text("PRIVATE_SYNTHETIC_CONTENT")
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output
    (batch,) = (tmp_path / "backups").iterdir()
    (root.root / "restore").mkdir()
    restored = root.root / "restore/session"
    result = cli(
        "restore", "verify", str(batch), "--target", str(restored), "--replay-container"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return restored, (
        root.database,
        root.data_root,
        root.config,
        root.root / "pi-materials",
        root.root / "pi-install",
        root.root / "models",
    )


def replay_args(restored: Path, originals: tuple[Path, ...]) -> tuple[str, ...]:
    return (
        "replay",
        "--restored",
        str(restored),
        "--original-database",
        str(originals[0]),
        "--original-data-root",
        str(originals[1]),
        "--original-config-root",
        str(originals[2]),
        *(
            part
            for path in originals[3:]
            for part in ("--original-material-root", str(path))
        ),
    )
