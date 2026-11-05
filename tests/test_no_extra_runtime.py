"""D1: extra门禁中的恢复子进程仍使用真实无extra解释器。"""

import json
import os
import subprocess
from pathlib import Path

from tests.no_extra_runtime import no_extra_python as no_extra_python


def test_recovery_python_has_no_sdk_and_uses_this_tree(no_extra_python: Path) -> None:
    root = Path(__file__).parents[1]
    script = """import importlib.metadata,json,sys
from pathlib import Path
for name in ('docling-slim','docling-core','torch','transformers'):
 try: importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError: pass
 else: raise AssertionError('SDK installed in recovery environment')
import paper_radar
assert Path(paper_radar.__file__).resolve().parents[2]==Path(sys.argv[1]).resolve()
print(json.dumps(list(sys.version_info[:2])))
"""
    result = subprocess.run(
        [str(no_extra_python), "-B", "-c", script, str(root)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[0] == 3
