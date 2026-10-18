"""执行公共服务的真实强杀断点;trace/audit只暂停,不替换任何I/O行为。"""

import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.pi_supply_process_support import received

EXECUTE = """
import os, sys, threading
from pathlib import Path
from paper_radar.pi_supply import execute_cleanup_plan
stage, ready, release = sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
stopped = False
removed = 0
def pause():
    global stopped
    if stopped: return
    stopped = True
    os.write(ready, b'R')
    os.read(release, 1)
def trace(frame, event, arg):
    if event != 'call': return trace
    name = frame.f_code.co_name
    filename = frame.f_code.co_filename
    if '/pi_supply/cleanup_' not in filename: return trace
    if stage == 'retired' and name == 'move_to_trash': pause()
    if name == '_record':
        phase = frame.f_locals.get('phase')
        if stage == 'renamed' and phase == 'moved': pause()
        if stage == 'deleted' and phase == 'completed': pause()
    return trace
def audit(event, args):
    global removed
    if event != 'os.remove': return
    frame = sys._getframe(1)
    if not frame.f_code.co_filename.endswith('/pi_supply/cleanup_delete.py'): return
    removed += 1
    if stage.startswith('partial-') and removed == int(stage.split('-')[1]): pause()
sys.addaudithook(audit)
sys.settrace(trace)
result = execute_cleanup_plan(Path(sys.argv[1]), sys.argv[2])
print(result.passed)
"""


@contextmanager
def interrupted_execution(
    database: Path, plan_id: str, stage: str
) -> Iterator[tuple[subprocess.Popen[bytes], int]]:
    ready_r, ready_w = os.pipe()
    release_r, release_w = os.pipe()
    process = subprocess.Popen(
        (
            sys.executable,
            "-c",
            EXECUTE,
            str(database),
            plan_id,
            stage,
            str(ready_w),
            str(release_r),
        ),
        pass_fds=(ready_w, release_r),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    os.close(ready_w)
    os.close(release_r)
    try:
        assert received(ready_r) == b"R"
        yield process, release_w
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
        for descriptor in (ready_r, release_w):
            os.close(descriptor)
