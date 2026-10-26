"""从安装包与可用 Git checkout 取得窄代码审计身份。"""

import subprocess
from importlib.metadata import version
from pathlib import Path

from paper_radar.fixture_audit.acquisition_models import CodeIdentity


def capture_code_identity() -> CodeIdentity:
    root = Path(__file__).resolve().parents[3]
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                timeout=2,
            ).stdout
        )
        return CodeIdentity(
            package_version=version("paper-radar"), commit=commit, dirty=dirty
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return CodeIdentity(package_version=version("paper-radar"))
