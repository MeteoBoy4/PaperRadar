"""仅启动合成 Python fixture;I/O 和清理由产品 PipeSession 承担。"""

import os
import select
import signal
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic

from paper_radar.llm.models import CallDescription
from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.llm.rpc_types import MonotonicClock

ROOT = Path(__file__).parents[1]


@dataclass(repr=False)
class FixtureFactory:
    scenario: str
    directory: Path
    status_read: int
    status_write: int
    baseline_fds: int
    own_group: bool = True
    clock: MonotonicClock = monotonic
    child: subprocess.Popen[bytes] | None = None
    session: PipeSession | None = None
    pidfds: list[int] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    tail: bytes = b""

    def collect(self) -> None:
        while True:
            try:
                data = os.read(self.status_read, 4096)
            except BlockingIOError:
                break
            if not data:
                break
            self.tail += data
            while b"\n" in self.tail:
                line, self.tail = self.tail.split(b"\n", 1)
                notice = line.decode()
                self.notices.append(notice)
                if notice.startswith("G"):
                    self.pidfds.append(os.pidfd_open(int(notice[1:])))

    def cancelled(self) -> bool:
        self.collect()
        return "P" in self.notices

    def __call__(self, description: CallDescription) -> PipeSession:
        assert self.child is None
        self.child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-s",
                str(ROOT / "tests/a8_pipe_worker.py"),
                self.scenario,
                description.system_prompt.decode(),
                str(self.status_write),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.directory,
            start_new_session=self.own_group,
            bufsize=0,
            pass_fds=(self.status_write,),
            env={
                "PYTHONPATH": str(ROOT / "tests/deny_external_io"),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        self.pidfds.append(os.pidfd_open(self.child.pid))
        os.close(self.status_write)
        self.status_write = -1
        deadline = monotonic() + 3
        while "R" not in self.notices or (
            self.scenario.startswith("grandchild")
            and not any(n.startswith("G") for n in self.notices)
        ):
            assert select.select(
                [self.status_read], [], [], max(0, deadline - monotonic())
            )[0], "fixture 未握手"
            self.collect()
        self.session = PipeSession(self.child, clock=self.clock)
        return self.session

    def assert_reclaimed(self) -> None:
        assert self.child is not None
        assert self.child.poll() is not None
        assert all(
            stream is not None and stream.closed
            for stream in (self.child.stdin, self.child.stdout, self.child.stderr)
        )
        for fd in self.pidfds:
            assert select.select([fd], [], [], 1)[0], "产品 wrapper 遗留活进程"
        assert len(os.listdir("/proc/self/fd")) == self.baseline_fds + 1 + len(
            self.pidfds
        )
        self.collect()
        assert list(self.directory.iterdir()) == []


@contextmanager
def fixture_factory(
    directory: Path,
    scenario: str,
    *,
    own_group: bool = True,
    clock: MonotonicClock = monotonic,
) -> Iterator[FixtureFactory]:
    baseline_fds = len(os.listdir("/proc/self/fd"))
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    factory = FixtureFactory(
        scenario, directory, read_fd, write_fd, baseline_fds, own_group, clock
    )
    try:
        yield factory
    finally:
        # 失败兜底放在所有无残留断言之后,不能冒充产品清理证据。
        if factory.child is not None:
            if factory.own_group:
                with suppress(ProcessLookupError):
                    os.killpg(factory.child.pid, signal.SIGKILL)
            elif factory.child.poll() is None:
                factory.child.kill()
            factory.child.wait(timeout=2)
            for stream in (
                factory.child.stdin,
                factory.child.stdout,
                factory.child.stderr,
            ):
                if stream is not None:
                    stream.close()
        for fd in (read_fd, factory.status_write, *factory.pidfds):
            if fd >= 0:
                os.close(fd)
