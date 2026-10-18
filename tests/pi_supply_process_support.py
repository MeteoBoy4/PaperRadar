"""真实 Python 父子双向管道握手;不以等待固定时长推断退出。"""

import contextlib
import os
import select
import signal
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

CHILD = """
import os, sys
lock, ready, release = map(int, sys.argv[1:])
os.fstat(lock)
os.write(ready, (str(os.getpid()) + '\\n').encode())
os.close(ready)
os.read(release, 1)
"""
PARENT = """
import os, sys, threading
from pathlib import Path
from paper_radar.pi_supply import use_install
from paper_radar.pi_supply.transport import ProcessRunner
ready, release, close_request, closed = map(int, sys.argv[3:7])
with use_install(Path(sys.argv[1]), sys.argv[2]) as handle:
    worker = threading.Thread(target=lambda: ProcessRunner().run(
        (sys.executable, '-c', sys.argv[7], str(handle.pass_fds[0]),
         str(ready), str(release)),
        cwd=Path.cwd(), env=dict(os.environ), timeout=30, limit=1024,
        pass_fds=(*handle.pass_fds, ready, release)))
    worker.start()
    os.read(close_request, 1)
os.write(closed, b'C')
worker.join()
"""


def received(descriptor: int) -> bytes:
    assert select.select([descriptor], [], [], 10)[0], "子进程握手超时"
    return os.read(descriptor, 128)


@contextmanager
def inherited_child(
    database: Path, snapshot: str
) -> Iterator[tuple[subprocess.Popen[bytes], int, int, int, int]]:
    ready_r, ready_w = os.pipe()
    release_r, release_w = os.pipe()
    request_r, request_w = os.pipe()
    closed_r, closed_w = os.pipe()
    process = subprocess.Popen(
        (
            sys.executable,
            "-c",
            PARENT,
            str(database),
            snapshot,
            str(ready_w),
            str(release_r),
            str(request_r),
            str(closed_w),
            CHILD,
        ),
        pass_fds=(ready_w, release_r, request_r, closed_w),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for descriptor in (ready_w, release_r, request_r, closed_w):
        os.close(descriptor)
    child = None
    death = None
    try:
        child = int(received(ready_r))
        death = os.pidfd_open(child)
        yield process, child, release_w, request_w, closed_r
        assert select.select([death], [], [], 10)[0], "子进程未确认退出"
    finally:
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(child, signal.SIGKILL)
        if death is not None:
            os.close(death)
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
        for descriptor in (ready_r, release_w, request_w, closed_r):
            os.close(descriptor)


CHECK_CHILD = """
import os, sys
lock, ready, release = map(int, sys.argv[1:])
os.fstat(lock)
os.write(ready, (str(os.getpid()) + '\\n').encode())
os.close(ready)
os.read(release, 1)
print('SECRET-process-output')
sys.exit(7)
"""
CHECK_PARENT = """
import os, sys
from pathlib import Path
from paper_radar.pi_supply import verify_supply
from paper_radar.pi_supply.transport import ProcessRunner
ready, release = map(int, sys.argv[3:5])
class Check:
    def run(self, argv, *, cwd, env, timeout, limit, pass_fds=()):
        return ProcessRunner().run(
            (sys.executable, '-c', sys.argv[6], str(pass_fds[0]),
             str(ready), str(release)),
            cwd=cwd, env=env, timeout=int(sys.argv[5]), limit=1024,
            pass_fds=(*pass_fds, ready, release))
try:
    result = verify_supply(Path(sys.argv[1]), sys.argv[2], runner=Check())
    print(result[0].reason)
except KeyboardInterrupt:
    print('operation_interrupted')
"""


@contextmanager
def checking_process(
    database: Path, supply_id: str, timeout: int
) -> Iterator[tuple[subprocess.Popen[bytes], int, int]]:
    ready_r, ready_w = os.pipe()
    release_r, release_w = os.pipe()
    process = subprocess.Popen(
        (
            sys.executable,
            "-c",
            CHECK_PARENT,
            str(database),
            supply_id,
            str(ready_w),
            str(release_r),
            str(timeout),
            CHECK_CHILD,
        ),
        pass_fds=(ready_w, release_r),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    os.close(ready_w)
    os.close(release_r)
    child = None
    try:
        child = int(received(ready_r))
        yield process, child, release_w
    finally:
        if process.poll() is None:
            process.kill()
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(child, signal.SIGKILL)
        process.communicate(timeout=10)
        os.close(ready_r)
        os.close(release_w)
