"""固定自有文件的本机 flock 追加与轮转,不订阅任何 logger。"""

import fcntl
import itertools
import json
import os
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path

from paper_radar.runtime_logging.schema import safe_event

MAX_BYTES = 1024 * 1024
MAX_FILES = 5
FILENAME = "runtime.jsonl"
LOCKNAME = ".runtime.lock"


@contextmanager
def regular(directory: int, name: str, flags: int) -> Iterator[int]:
    descriptor = os.open(
        name,
        flags | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
        0o600,
        dir_fd=directory,
    )
    try:
        value = os.fstat(descriptor)
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
            raise OSError("unsafe_log_file")
        yield descriptor
    finally:
        os.close(descriptor)


class FileSink:
    def __init__(
        self, root: Path, *, max_bytes: int = MAX_BYTES, max_files: int = MAX_FILES
    ) -> None:
        if max_bytes < 1 or max_files < 1:
            raise ValueError("invalid_log_limits")
        self.root, self.max_bytes, self.max_files = root, max_bytes, max_files

    def emit(self, event: Mapping[str, object]) -> None:
        payload = (json.dumps(safe_event(event), ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        if len(payload) > self.max_bytes:
            raise ValueError("log_event_too_large")
        self.root.mkdir(parents=True, exist_ok=True)
        root = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            with suppress(FileExistsError):
                os.mkdir("logs", 0o700, dir_fd=root)
            directory = os.open(
                "logs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root
            )
        finally:
            os.close(root)
        try:
            with regular(directory, LOCKNAME, os.O_RDWR | os.O_CREAT) as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                self._append(directory, payload)
        finally:
            os.close(directory)

    def _append(self, directory: int, payload: bytes) -> None:
        with regular(
            directory, FILENAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND
        ) as active:
            size = os.fstat(active).st_size
        if size and size + len(payload) > self.max_bytes:
            names = [FILENAME] + [f"{FILENAME}.{n}" for n in range(1, self.max_files)]
            # 先核验全部候选,避免中途发现链接而已移动部分历史。
            for name in names:
                try:
                    with regular(directory, name, os.O_RDONLY):
                        pass
                except FileNotFoundError:
                    pass
            if self.max_files == 1:
                with regular(directory, FILENAME, os.O_WRONLY) as active:
                    os.ftruncate(active, 0)
            else:
                with suppress(FileNotFoundError):
                    os.unlink(names[-1], dir_fd=directory)
                for source, target in reversed(list(itertools.pairwise(names))):
                    with suppress(FileNotFoundError):
                        os.rename(
                            source, target, src_dir_fd=directory, dst_dir_fd=directory
                        )
        with regular(
            directory, FILENAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND
        ) as active:
            original_size = os.fstat(active).st_size
            remaining = memoryview(payload)
            try:
                while remaining:
                    written = os.write(active, remaining)
                    if written <= 0:
                        raise OSError("log_write_failed")
                    remaining = remaining[written:]
            except Exception:
                # 持同一 flock 撤去本次半行;不重试、不补写事件。
                with suppress(OSError):
                    os.ftruncate(active, original_size)
                raise
