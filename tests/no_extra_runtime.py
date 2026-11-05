"""恢复测试的真实基础解释器端口;不把禁SDK导入当作未安装。"""

import fcntl
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PORT = "PAPERRADAR_NO_EXTRA_PYTHON"
_PROBE = """import importlib.metadata,importlib.util,sys
from pathlib import Path
assert tuple(sys.version_info[:2])==tuple(map(int,sys.argv[2].split('.')))
for name in ('docling-slim','docling-core','torch','torchvision',
             'transformers','docling-parse','pypdfium2'):
 try: importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError: pass
 else: raise AssertionError('recovery requires actual no-extra environment')
for name in ('docling','docling_core','torch','torchvision',
             'transformers','docling_parse','pypdfium2'):
 assert importlib.util.find_spec(name) is None
sys.path.insert(0,str(Path(sys.argv[1])/'src'))
import paper_radar
from paper_radar.body import BodyService
assert Path(paper_radar.__file__).resolve().parents[2]==Path(sys.argv[1]).resolve()
"""


def _valid(python: Path) -> bool:
    try:
        result = subprocess.run(
            [
                str(python),
                "-I",
                "-B",
                "-c",
                _PROBE,
                str(ROOT),
                f"{sys.version_info.major}.{sys.version_info.minor}",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.fixture(scope="session")
def no_extra_python() -> Path:
    """显式端口优先;否则当前基础环境或同minor离线磁盘base+dev。"""
    explicit = os.environ.get(PORT)
    if explicit:
        python = Path(explicit).absolute()
        if not _valid(python):
            pytest.fail(f"{PORT} 必须指向同minor、实际无SDK的基础解释器")
        return python
    current = Path(sys.executable)
    if _valid(current):
        return current
    environments = ROOT / ".scratch/test-environments"
    environments.mkdir(parents=True, exist_ok=True)
    environment = (
        environments
        / f"no-extra-cpython-{sys.version_info.major}.{sys.version_info.minor}"
    )
    python = environment / "bin/python"
    # 多个pytest进程可共享供给,仅序列化本测试环境的离线安装。
    with (environments / "no-extra.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not _valid(python):
            env = dict(os.environ)
            env["UV_PROJECT_ENVIRONMENT"] = str(environment)
            env["UV_PYTHON_DOWNLOADS"] = "never"
            env.pop("UV_EXTRA", None)
            env.pop("UV_ALL_EXTRAS", None)
            result = subprocess.run(
                [
                    "uv",
                    "sync",
                    "--offline",
                    "--locked",
                    "--group",
                    "dev",
                    "--no-extra",
                    "docling",
                    "--python",
                    str(current),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0 or not _valid(python):
                pytest.fail("无法离线准备恢复基础环境;请预先同步base+dev或设置 " + PORT)
    return python
