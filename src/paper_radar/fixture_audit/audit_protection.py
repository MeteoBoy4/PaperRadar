"""计划粒度的短时非阻塞 flock,独立于模型任务与 Pi 安装保护。"""

from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
from types import TracebackType

from paper_radar.fixture_audit.errors import FixtureError, FixtureReason


class AuditProtection:
    def __init__(self, database: Path, data_root: Path | None, plan_id: str) -> None:
        self.database, self.data_root, self.plan_id = database, data_root, plan_id
        self.fd: int | None = None

    def __enter__(self) -> AuditProtection:
        database = self.database.resolve()
        namespace = hashlib.sha256(os.fsencode(database)).hexdigest()
        directory = database.parent.parent / ".paper-radar-audit-locks" / namespace
        if self.data_root is None or directory.is_relative_to(self.data_root.resolve()):
            raise FixtureError(FixtureReason.INVALID_REQUEST, path="data_root")
        try:
            if directory.is_symlink() or directory.parent.is_symlink():
                raise FixtureError(FixtureReason.INVALID_REQUEST, path="audit_lock")
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or directory.parent.is_symlink():
                raise FixtureError(FixtureReason.INVALID_REQUEST, path="audit_lock")
            fd = os.open(
                directory / f"{self.plan_id}.lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
            )
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise FixtureError(
                    FixtureReason.EXECUTION_BUSY, path="plan_id"
                ) from None
            self.fd = fd
            return self
        except OSError:
            raise FixtureError(
                FixtureReason.INVALID_REQUEST, path="audit_lock"
            ) from None

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
