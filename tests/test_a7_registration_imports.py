"""论文包保留零外部I/O启动边界;事务组合接口仅显式消费时加载。"""

import os
import subprocess
import sys
from pathlib import Path


def test_public_paper_vocabulary_import_stays_safe_for_cli_help(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from paper_radar.papers import PaperReason; "
            "print(PaperReason.MISSING_ABSTRACT.value)",
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "missing_abstract"
    assert not tuple(tmp_path.iterdir())
