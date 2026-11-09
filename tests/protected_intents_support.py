"""只替换inode标志系统调用的无root模型;不把它当本机+a证明。"""

import os
import weakref
from pathlib import Path

import pytest

from paper_radar.live_evidence.intents import FS_APPEND_FL, ProtectedIntentLog
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from tests.live_evidence_ledger_support import NOW, owner_uid


class AppendOnlyKernel:
    def __init__(self) -> None:
        self.flags: dict[tuple[int, int], int] = {}
        self.pins: list[int] = []
        weakref.finalize(self, self._close, self.pins)

    @staticmethod
    def _close(pins: list[int]) -> None:
        for fd in pins:
            os.close(fd)

    def get_flags(self, fd: int) -> int:
        info = os.fstat(fd)
        return self.flags.get((info.st_dev, info.st_ino), 0)

    def set_append_only(self, fd: int) -> None:
        info = os.fstat(fd)
        self.flags[(info.st_dev, info.st_ino)] = FS_APPEND_FL
        self.pins.append(os.dup(fd))

    def mutate(self, path: Path, operation: str, previous: bytes = b"") -> None:
        info = path.stat()
        if self.flags.get((info.st_dev, info.st_ino), 0) & FS_APPEND_FL:
            raise PermissionError("append_only_kernel_denied")
        if operation == "delete":
            path.unlink()
        elif operation in {"truncate", "overwrite", "rollback"}:
            path.write_bytes(previous)
        elif operation == "replace":
            replacement = path.with_suffix(".old")
            replacement.write_bytes(previous)
            replacement.replace(path)
        elif operation == "hardlink":
            os.link(path, path.with_suffix(".link"))
        else:
            raise ValueError("model_operation_invalid")


def intent_log(
    ledger: EvidenceLedger, monkeypatch: pytest.MonkeyPatch, *, path: Path | None = None
) -> tuple[ProtectedIntentLog, AppendOnlyKernel]:
    from paper_radar.live_evidence import intents, service

    selected = ledger.root.parent / "pending.jsonl" if path is None else path
    selected.parent.chmod(0o755)
    log = ProtectedIntentLog(
        selected,
        product_gid=os.getgid(),
        trust=LedgerTrust(owner_uid(), owner_uid() + 1, selected.parent),
    )
    kernel = AppendOnlyKernel()
    monkeypatch.setattr(intents, "_get_flags", kernel.get_flags)
    monkeypatch.setattr(intents, "_set_append_only", kernel.set_append_only)
    log.provision(ledger, now=NOW)
    monkeypatch.setattr(service, "_intents", lambda: log)
    return log, kernel
