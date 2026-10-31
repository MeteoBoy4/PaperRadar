"""仓库副本重绑与现有 writer 调用机制;审阅白名单和预期由调用方维护。"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tests.a2_full_support import repository_copy


def prepared_repository(
    target: Path, *, reviewed: frozenset[str], verified_groups: frozenset[str]
) -> Path:
    """只在隔离副本接受已审阅路径及原 scope DAG 传播,拒绝意外漂移。"""
    root = repository_copy(target)
    program = r"""
import hashlib
import re
from pathlib import Path
from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_registry import load_scopes
root = Path.cwd()
report = audit_scopes(root, load_scopes(root))
assert not report['issues'], report['issues']
reviewed = REVIEWED | set(report['order'])
unexpected = [row for row in report['files']
              if row['reason'] != 'ok' and row['path'] not in reviewed]
assert not unexpected, unexpected
pattern = re.compile(r'(\(\s*"([^"]+)",\s*")([0-9a-f]{64})(")')
def replacement(match):
    relative = match[2]
    if relative not in reviewed:
        return match[0]
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    return match[1] + digest + match[4]
for relative in report['order']:
    path = root / relative
    path.write_text(pattern.sub(replacement, path.read_text()))
report = audit_scopes(root, load_scopes(root))
assert not report['issues'], report['issues']
assert report['exit_code'] == 0, report
assert all(row['reason'] == 'ok' for row in report['files']
           if row['group'] in VERIFIED_GROUPS), report['files']
"""
    program = program.replace("REVIEWED", repr(set(reviewed))).replace(
        "VERIFIED_GROUPS", repr(set(verified_groups))
    )
    subprocess.run((sys.executable, "-B", "-c", program), cwd=root, check=True)
    return root


def writer_conclusion(root: Path, output: Path, group: int) -> dict[str, Any]:
    """在副本的冷进程调用现有组支撑,不制造正式执行回执。"""
    assert group in (8, 9, 10)
    output.mkdir()
    program = f"""
import json
from pathlib import Path
from tests.a{group}_acceptance_support import conclude, same_a{group}_run
root = Path.cwd()
output = Path({str(output)!r})
_, result = conclude(output, same_a{group}_run(output, root=root), root=root)
print(json.dumps(result))
"""
    result = subprocess.run(
        (sys.executable, "-B", "-c", program),
        cwd=root,
        capture_output=True,
        check=True,
    )
    value: dict[str, Any] = json.loads(result.stdout)
    return value
