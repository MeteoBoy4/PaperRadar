"""Popen 与 PipeSession 交接失败时的有限回收;不记录任何子进程输出。"""

import os
import selectors
import signal
import subprocess
from contextlib import suppress
from time import monotonic

from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.pi_execution.errors import ExecutionError


def adopt_process(child: subprocess.Popen[bytes]) -> PipeSession:
    try:
        return PipeSession(child)
    except BaseException:
        deadline = monotonic() + 10
        pidfds: list[int] = []
        try:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=max(0, deadline - monotonic()))
            with (
                os.scandir("/proc") as processes,
                selectors.DefaultSelector() as exited,
            ):
                for entry in processes:
                    if monotonic() >= deadline:
                        raise ExecutionError("cleanup_failed")
                    if not entry.name.isdecimal():
                        continue
                    try:
                        pid = int(entry.name)
                        if os.getpgid(pid) != child.pid:
                            continue
                        fd = os.pidfd_open(pid)
                    except ProcessLookupError:
                        continue
                    pidfds.append(fd)
                    exited.register(fd, selectors.EVENT_READ)
                while exited.get_map():
                    left = deadline - monotonic()
                    if left <= 0:
                        raise ExecutionError("cleanup_failed")
                    for key, _mask in exited.select(left):
                        exited.unregister(key.fd)
        finally:
            for fd in pidfds:
                os.close(fd)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
        raise
