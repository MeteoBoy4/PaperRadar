"""Popen 与 PipeSession 交接失败时的有限回收;不记录任何子进程输出。"""

import ctypes
import os
import selectors
import signal
import subprocess
from contextlib import suppress
from pathlib import Path
from time import monotonic

from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import IsolationBoundary, disable_core_dumps


def _auth_boundary() -> None:
    disable_core_dumps()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(39, 0, 0, 0, 0) != 1:
        raise ExecutionError("isolation_unavailable")


def spawn_unplaced(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    env: dict[str, str],
    install: Path,
    attempt: Path | None,
    proxy_port: int | None,
    pass_fds: tuple[int, ...],
) -> subprocess.Popen[bytes]:
    """显式豁免后的宿主 resolver 路径;仍在 exec 前建立原隔离边界。"""
    return subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=pass_fds,
        start_new_session=True,
        umask=0o077,
        preexec_fn=(
            _auth_boundary
            if attempt is None
            else IsolationBoundary(install, cwd, attempt, proxy_port)
        ),
    )


def adopt_process(child: subprocess.Popen[bytes]) -> PipeSession:
    try:
        return PipeSession(child)
    except BaseException:
        cleanup_process(child)
        raise


def cleanup_process(child: subprocess.Popen[bytes]) -> None:
    """按已取得的独立进程组有界回收,包括已退出leader留下的子进程。"""
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
