"""历史来源回放的冷进程边界:任务导入不取得LLM或供给执行能力。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HISTORY_GUARD = """
import importlib.abc
import json
import sys

prefixes = tuple(json.loads(sys.argv[1]))

class HistoryOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == prefix or fullname.startswith(prefix + '.')
               for prefix in prefixes):
            raise RuntimeError('execution_import_forbidden:' + fullname)

def no_runtime_io(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty',
                 'os.exec', 'os.posix_spawn', 'socket.connect',
                 'socket.__new__', 'socket.getaddrinfo'}:
        raise RuntimeError('runtime_io_forbidden:' + event)
    if event == 'sqlite3.connect' and len(sys.argv) == 2:
        raise RuntimeError('runtime_io_forbidden:' + event)

sys.meta_path.insert(0, HistoryOnly())
sys.addaudithook(no_runtime_io)
"""

_COLD_IMPORT = (
    _HISTORY_GUARD
    + """
from paper_radar.screening_tasks import ScreeningTasks
assert callable(ScreeningTasks)
print(json.dumps({'history_import_only': True}))
"""
)

_COLD_REPLAY = (
    _HISTORY_GUARD
    + """
from pathlib import Path
from paper_radar.backup import restore_backup, verify_backup
from paper_radar.screening_tasks import ScreeningTasks

batch, target, success_id, paper_id, snapshot_id = sys.argv[2:]
verify_backup(Path(batch))
restored = restore_backup(Path(batch), Path(target))
tasks = ScreeningTasks(Path(target) / 'database.sqlite3', Path(target))
loaded = tasks.load_success(success_id)
assert loaded.raw_response == (
    b'{"boundary":"in_scope","reason_zh":"Atmospheric processes."}'
)
assert loaded.receipt.executor_kind == 'pi_rpc'
assert len(tasks.query_successes(
    paper_id=paper_id, stage='boundary', snapshot_id=snapshot_id
)) == 1
tasks.validate_all()
print(json.dumps({'history_replay_only': True}))
"""
)


@pytest.mark.parametrize(
    "forbidden",
    [
        ["paper_radar.llm"],
        [
            "paper_radar.pi_supply.service",
            "paper_radar.pi_supply.transport",
            "paper_radar.pi_supply.protection",
            "paper_radar.pi_supply.execution",
            "httpx",
        ],
    ],
    ids=["llm", "supply-execution"],
)
def test_task_history_import_cannot_load_execution_modules_or_perform_io(
    tmp_path: Path, forbidden: list[str]
) -> None:
    child = subprocess.run(
        [sys.executable, "-B", "-c", _COLD_IMPORT, json.dumps(forbidden)],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout) == {"history_import_only": True}


def test_pi_rpc_restore_and_query_do_not_import_execution_implementations(
    tmp_path: Path,
) -> None:
    from paper_radar.backup import create_backup
    from paper_radar.screening_tasks import ScreeningTasks, SuccessReceipt
    from tests.a8_call_support import request_for
    from tests.pi_rpc_source_support import NOW, candidate, source_archive

    root = tmp_path / "original"
    root.mkdir()
    data, supplied = source_archive(root)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    success = tasks.run_once(receipt.receipt_id, lambda *_: candidate(data, supplied))
    assert isinstance(success, SuccessReceipt)
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    # 完整备份还回放既有Feed闭包,其纯header helper会导入httpx。
    # 此处禁止供给HTTP/进程实现,同时audit拒绝任何实际网络和子进程。
    forbidden = [
        "paper_radar.llm",
        "paper_radar.pi_supply.service",
        "paper_radar.pi_supply.transport",
        "paper_radar.pi_supply.protection",
        "paper_radar.pi_supply.execution",
    ]
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _COLD_REPLAY,
            json.dumps(forbidden),
            str(batch.batch_dir),
            str(tmp_path / "restored"),
            success.success_id,
            data.paper_id,
            data.snapshot_id,
        ],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout) == {"history_replay_only": True}
