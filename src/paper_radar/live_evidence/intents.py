"""固定root只追加收紧日志;产品无创建、截断、轮转或恢复通道。"""

from __future__ import annotations

import array
import fcntl
import os
import platform
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError, LedgerTrust
from paper_radar.live_evidence.receipt import WireModel

INTENT_PATH = Path("/var/lib/paperradar/live-evidence-intents/pending.jsonl")
MAX_INTENT_BYTES = 8 * 1024 * 1024
MAX_INTENT_LINE = 16 * 1024
FS_APPEND_FL = 0x20
FS_IMMUTABLE_FL = 0x10
CUTOVER_REASON = "append-only-v1"


class IntentHeader(WireModel):
    format_version: Literal[1] = 1
    record_type: Literal["cutover"] = "cutover"
    sequence: int = Field(ge=1, strict=True)
    recorded_at: datetime


def _flags_command(*, write: bool) -> int:
    # 本项目的已知Linux64位通用ioctl ABI;未知平台拒绝,不猜编号。
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise LedgerError("pending_revocation_unavailable")
    return 0x40086602 if write else 0x80086601


def _get_flags(fd: int) -> int:
    flags = array.array("I", [0])
    fcntl.ioctl(fd, _flags_command(write=False), flags, True)
    return flags[0]


def _set_append_only(fd: int) -> None:
    flags = array.array("I", [_get_flags(fd) | FS_APPEND_FL])
    fcntl.ioctl(fd, _flags_command(write=True), flags, True)


class ProtectedIntentLog:
    """可替换OS信任仅供离线fixture;产品工厂不接收外部路径或策略。"""

    def __init__(
        self,
        path: Path = INTENT_PATH,
        *,
        product_gid: int | None = None,
        trust: LedgerTrust | None = None,
    ) -> None:
        self.path = path.absolute()
        self.product_gid = os.getgid() if product_gid is None else product_gid
        self.trust = LedgerTrust() if trust is None else trust

    def _directories(self, path: Path, *, private: bool = False) -> None:
        anchor = self.trust.anchor.absolute()
        if not path.is_relative_to(anchor):
            raise LedgerError("pending_revocation_unavailable")
        while True:
            info = path.lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid != self.trust.owner_uid
                or info.st_mode & 0o022
            ):
                raise LedgerError("pending_revocation_unavailable")
            if path == self.path.parent and stat.S_IMODE(info.st_mode) != (
                0o700 if private else 0o755
            ):
                raise LedgerError("pending_revocation_unavailable")
            if path == anchor:
                return
            path = path.parent

    def _checked_fd(self, *, write: bool, private: bool = False) -> int:
        self._directories(self.path.parent, private=private)
        flags = os.O_WRONLY | os.O_APPEND if write else os.O_RDONLY
        fd = os.open(self.path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self.trust.owner_uid
                or info.st_gid != self.product_gid
                or stat.S_IMODE(info.st_mode) != 0o660
                or info.st_nlink != 1
                or info.st_size > MAX_INTENT_BYTES
                or _get_flags(fd) & (FS_APPEND_FL | FS_IMMUTABLE_FL) != FS_APPEND_FL
            ):
                raise LedgerError("pending_revocation_unavailable")
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _header(data: bytes) -> IntentHeader:
        try:
            return IntentHeader.model_validate_json(data)
        except (ValidationError, ValueError) as error:
            raise LedgerError("pending_revocation_unavailable") from error

    def read(self, ledger: EvidenceLedger) -> tuple[bytes, ...]:
        """缺失不是空日志;首记录须匹配同一root账本cutover事件。"""
        try:
            fd = self._checked_fd(write=False)
            with os.fdopen(fd, "rb") as stream:
                data = stream.read(MAX_INTENT_BYTES + 1)
            lines = data.splitlines()
            if (
                not data.endswith(b"\n")
                or not lines
                or len(data) >= MAX_INTENT_BYTES
                or any(not line or len(line) + 1 > MAX_INTENT_LINE for line in lines)
            ):
                raise LedgerError("pending_revocation_unavailable")
            header = self._header(lines[0])
            if not any(
                event.sequence == header.sequence
                and event.action == "evidence_intent_cutover"
                and event.subject_id == "ledger"
                and event.recorded_at == header.recorded_at
                and event.reason == CUTOVER_REASON
                for event in ledger.audit()
            ):
                raise LedgerError("pending_revocation_unavailable")
            return tuple(lines[1:])
        except (OSError, ValueError) as error:
            raise LedgerError("pending_revocation_unavailable") from error

    def append(self, data: bytes) -> None:
        """只追加一个规范记录;无O_CREAT或回退路径,短写/落盘失败不称成功。"""
        if b"\n" in data or not data or len(data) + 1 > MAX_INTENT_LINE:
            raise LedgerError("pending_revocation_unavailable")
        try:
            # 先核固定首记录与标志,即使账本暂不可读仍可追加拒绝。
            read_fd = self._checked_fd(write=False)
            with os.fdopen(read_fd, "rb") as stream:
                first = stream.readline(MAX_INTENT_LINE + 1)
            if not first.endswith(b"\n") or len(first) > MAX_INTENT_LINE:
                raise LedgerError("pending_revocation_unavailable")
            self._header(first)
            fd = self._checked_fd(write=True)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                if os.fstat(fd).st_size + len(data) + 1 >= MAX_INTENT_BYTES:
                    raise LedgerError("pending_revocation_unavailable")
                if os.write(fd, data + b"\n") != len(data) + 1:
                    raise LedgerError("pending_revocation_unavailable")
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as error:
            raise LedgerError("pending_revocation_unavailable") from error

    def provision(self, ledger: EvidenceLedger, *, now: datetime) -> bool:
        """仅owner冻结部署;先永久切断旧资格,不把缺失日志当干净。"""
        ledger._writer()
        if os.geteuid() != self.trust.owner_uid:
            raise LedgerError("protected_entry_required")
        try:
            if os.path.lexists(self.path):
                self.read(ledger)
                return False
            if not self.path.parent.exists():
                self._directories(self.path.parent.parent)
                self.path.parent.mkdir(mode=0o700)
            else:
                self._directories(self.path.parent)
                os.chmod(self.path.parent, 0o700)
            # 先持久封闭目录,避免0660 inode在+a前被产品抢先取得写fd。
            self._directories(self.path.parent, private=True)
            for path in (self.path.parent, self.path.parent.parent):
                directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

            event = EvidenceLifecycle(ledger).cutover_intents(now=now)
            header = IntentHeader(
                sequence=event.sequence, recorded_at=event.recorded_at
            )
            fd = os.open(
                self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            try:
                data = header.model_dump_json().encode() + b"\n"
                if os.write(fd, data) != len(data):
                    raise LedgerError("pending_revocation_unavailable")
                os.fchown(fd, self.trust.owner_uid, self.product_gid)
                os.fchmod(fd, 0o660)
                os.fsync(fd)
                _set_append_only(fd)
                os.fsync(fd)
            finally:
                os.close(fd)
            check = self._checked_fd(write=False, private=True)
            with os.fdopen(check, "rb") as stream:
                if stream.read(MAX_INTENT_LINE + 1) != data:
                    raise LedgerError("pending_revocation_unavailable")
            os.chmod(self.path.parent, 0o755)
            directory = os.open(
                self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            self.read(ledger)
            return True
        except (OSError, ValueError) as error:
            if isinstance(error, LedgerError):
                raise
            raise LedgerError("pending_revocation_unavailable") from error
