"""本机同根Read显式执行串行资源;等待在auth与领取之前。"""

import fcntl
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from paper_radar.read_tasks.models import ReadTaskError

LOCK_FILENAME = ".body-read.lock"


@contextmanager
def execution_resource(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(
            root / LOCK_FILENAME,
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
    except OSError:
        raise ReadTaskError("invalid_request") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ReadTaskError("invalid_request")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)
