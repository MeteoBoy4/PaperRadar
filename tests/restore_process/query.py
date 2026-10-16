"""在没有原根目录的新进程中通过公共入口完整回放。"""

import json
import sys
from pathlib import Path

from tests.restore_support import history_view

root = Path(sys.argv[1])
expected = json.loads(Path(sys.argv[2]).read_bytes())
assert history_view(root / "database.sqlite3", root) == expected
print("历史配置与制品完整回放通过")
