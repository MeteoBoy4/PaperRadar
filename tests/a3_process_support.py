"""A3 真实子进程的有界管道屏障;启动钩子仅依赖标准库。"""

import os
import select
import subprocess
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path


def checkpoint() -> None:
    os.write(int(os.environ["A3_READY_FD"]), b"R")
    os.read(int(os.environ["A3_RELEASE_FD"]), 1)


@contextmanager
def paused_subprocess(
    command: list[str],
    hook_directory: Path,
    environment: Mapping[str, str],
    timeout_message: str,
    exit_message: str,
) -> Iterator[tuple[subprocess.Popen[str], int]]:
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()
    try:
        try:
            process = subprocess.Popen(
                command,
                env={
                    "PATH": os.environ["PATH"],
                    "PYTHONPATH": os.pathsep.join(
                        (str(hook_directory), str(Path(__file__).parent.parent))
                    ),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    **environment,
                    "A3_READY_FD": str(ready_write),
                    "A3_RELEASE_FD": str(release_read),
                },
                pass_fds=(ready_write, release_read),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        finally:
            os.close(ready_write)
            os.close(release_read)
        try:
            readable, _, _ = select.select([ready_read], [], [], 15)
            assert readable, timeout_message
            assert os.read(ready_read, 1) == b"R", exit_message
            yield process, release_write
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=15)
    finally:
        os.close(ready_read)
        os.close(release_write)
