"""映射真实进程屏障与来源文件读取哨兵。"""

import os
import runpy
import sys
from pathlib import Path

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
paused = False


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused
    if (
        os.environ.get("MAPPING_PAUSE")
        and statement.startswith("SELECT paper_versions")
        and not paused
    ):
        paused = True
        checkpoint()


def audit(name, args):  # type: ignore[no-untyped-def]
    if name == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        candidate = os.fsdecode(args[0])
        forbidden = os.environ.get("MAPPING_FORBIDDEN", "")
        if forbidden and candidate.startswith(forbidden):
            raise AssertionError("mapping attempted source blob I/O")


sys.addaudithook(audit)
