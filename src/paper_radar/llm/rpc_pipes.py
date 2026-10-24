"""已启动独立进程组的有界二进制管道;没有命令或环境构造能力。"""

import io
import math
import os
import selectors
import signal
import subprocess
from contextlib import suppress
from time import monotonic

from paper_radar.llm.rpc_types import (
    DEFAULT_LIMITS,
    MonotonicClock,
    RpcProblem,
    RpcReason,
    SessionEvent,
)

_CHUNK = 64 * 1024


class PipeSession:
    """接管干净的 binary Popen pipes;启动与拒绝接管后的回收归调用方。"""

    def __init__(
        self, process: subprocess.Popen[bytes], *, clock: MonotonicClock = monotonic
    ) -> None:
        # 验证之前不取得所有权,也绝不向未经验证的进程组发信号。
        if os.getpgid(process.pid) != process.pid or any(
            stream is None or stream.closed or isinstance(stream, io.TextIOBase)
            for stream in (process.stdin, process.stdout, process.stderr)
        ):
            raise RpcProblem(RpcReason.STARTUP_ERROR)
        self._process = process
        self._clock = clock
        self._selector = selectors.DefaultSelector()
        self._stdin = process.stdin
        self._stdout = process.stdout
        self._stderr = process.stderr
        self._finished = False
        self._stdout_eof = False
        self._stderr_eof = False
        try:
            for stream in (self._stdin, self._stdout, self._stderr):
                assert stream is not None
                os.set_blocking(stream.fileno(), False)
            assert self._stdout is not None and self._stderr is not None
            self._selector.register(
                self._stdout.fileno(), selectors.EVENT_READ, "stdout"
            )
            self._selector.register(
                self._stderr.fileno(), selectors.EVENT_READ, "stderr"
            )
        except BaseException:
            with suppress(Exception):
                self.terminate(DEFAULT_LIMITS.terminate)
            raise

    def pump(self, pending: bytes, timeout: float, /) -> SessionEvent:
        """每个 ready fd 至多一个非阻塞块;不给洪泛流无限 drain 的机会。"""
        if self._finished or not math.isfinite(timeout) or timeout < 0:
            raise RpcProblem(RpcReason.TRANSPORT_ERROR)
        stdin = self._stdin
        if stdin is not None and not stdin.closed:
            fd = stdin.fileno()
            if pending and fd not in self._selector.get_map():
                self._selector.register(fd, selectors.EVENT_WRITE, "stdin")
            elif not pending and fd in self._selector.get_map():
                self._selector.unregister(fd)
        elif pending:
            raise RpcProblem(RpcReason.TRANSPORT_ERROR)
        written = 0
        stdout = b""
        stderr_bytes = 0
        ready = self._selector.select(min(timeout, DEFAULT_LIMITS.poll))
        for key, _mask in ready:
            try:
                if key.data == "stdin":
                    written = os.write(key.fd, pending[:_CHUNK])
                    continue
                data = os.read(key.fd, _CHUNK)
            except BlockingIOError:
                continue
            if key.data == "stdout":
                stdout = data
            else:
                stderr_bytes += len(data)
            if not data:
                self._selector.unregister(key.fd)
                if key.data == "stdout":
                    self._stdout_eof = True
                    assert self._stdout is not None
                    self._stdout.close()
                else:
                    self._stderr_eof = True
                    assert self._stderr is not None
                    self._stderr.close()
        return SessionEvent(
            written=written,
            stdout=stdout,
            stderr_bytes=stderr_bytes,
            stdout_eof=self._stdout_eof,
            stderr_eof=self._stderr_eof,
            exit_code=self._process.poll(),
        )

    def close_stdin(self) -> None:
        """即时半关闭,不 flush/communicate/wait;所有实际写入均走 raw os.write。"""
        if self._stdin is not None and not self._stdin.closed:
            fd = self._stdin.fileno()
            if fd in self._selector.get_map():
                self._selector.unregister(fd)
            self._stdin.close()

    def terminate(self, timeout: float, /) -> None:
        """无论 leader 是否退出都清整组,有界等待 pidfd 并回收直接子进程。"""
        if self._finished:
            return
        if not math.isfinite(timeout) or timeout <= 0:
            raise RpcProblem(RpcReason.CLOSE_TIMEOUT)
        deadline = self._clock() + min(timeout, DEFAULT_LIMITS.terminate)
        try:
            with suppress(ProcessLookupError):
                os.killpg(self._process.pid, signal.SIGKILL)
            self.close_stdin()
            # EOF/leader 退出无法观察已主动关闭 pipe 的孙进程。Linux pidfd 证明
            # 组内进程真正退出,也避免用 kill(pid,0) 把 zombie 当作存活。
            try:
                self._wait_group(deadline)
            except BaseException:
                # 枚举/等待组失败也要尝试回收已被 kill 的直接 child,不覆盖原异常。
                with suppress(Exception):
                    self._process.wait(timeout=max(0.0, deadline - self._clock()))
                raise
            try:
                self._process.wait(timeout=max(0.0, deadline - self._clock()))
            except subprocess.TimeoutExpired:
                raise RpcProblem(RpcReason.CLOSE_TIMEOUT) from None
        finally:
            self._finished = True
            self._selector.close()
            for stream in (self._stdin, self._stdout, self._stderr):
                if stream is not None:
                    stream.close()

    def _wait_group(self, deadline: float) -> None:
        pidfds: list[int] = []
        try:
            with (
                os.scandir("/proc") as processes,
                selectors.DefaultSelector() as exited,
            ):
                for entry in processes:
                    if self._clock() >= deadline:
                        raise RpcProblem(RpcReason.CLOSE_TIMEOUT)
                    if not entry.name.isdecimal():
                        continue
                    pid = int(entry.name)
                    try:
                        if os.getpgid(pid) != self._process.pid:
                            continue
                        fd = os.pidfd_open(pid)
                    except ProcessLookupError:
                        continue
                    pidfds.append(fd)
                    exited.register(fd, selectors.EVENT_READ)
                while exited.get_map():
                    left = deadline - self._clock()
                    if left <= 0:
                        raise RpcProblem(RpcReason.CLOSE_TIMEOUT)
                    for key, _mask in exited.select(left):
                        exited.unregister(key.fd)
        finally:
            for fd in pidfds:
                os.close(fd)
