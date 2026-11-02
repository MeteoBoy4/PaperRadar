"""未绑定pytest失败的辅助定位;只允许仓库测试模块与受控阶段。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import suppress
from pathlib import Path

from scripts.verification_groups import receipt_modules

_PHASES = {"setup", "call", "teardown", "collection"}
_MODULE = re.compile(r"tests/test_[a-zA-Z0-9_]+\.py")
_MAX_BYTES = 1024 * 1024


def _modules(root: Path) -> set[str]:
    """只接受仓库顶层普通测试文件,不能来自nodeid参数或任意用户路径。"""
    fixed = set(receipt_modules())
    return {
        f"tests/{path.name}"
        for path in (root / "tests").glob("test_*.py")
        if path.is_file()
        and not path.is_symlink()
        and _MODULE.fullmatch(f"tests/{path.name}")
        and f"tests/{path.name}" not in fixed
    }


def _sidecar(receipt: Path) -> Path:
    return receipt.with_suffix(".failures.json")


def _read_bounded(path: Path) -> bytes:
    # 以非阻塞/不跟随链接的描述符核对普通文件,避免坏sidecar成为FIFO阻塞入口。
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError
        raw = stream.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise ValueError
        return raw


class FailureDiagnostics:
    def __init__(self, receipt: Path, run_id: str, root: Path) -> None:
        self.receipt, self.run_id = receipt, run_id
        self.allowed = _modules(root)
        self.failures: set[tuple[str, str]] = set()

    def record(self, nodeid: str, phase: str) -> None:
        module = nodeid.split("::", 1)[0]
        if module in self.allowed and phase in _PHASES:
            self.failures.add((module, phase))
            self.write()

    def write(self) -> None:
        # 成功/仅固定组失败不生成辅助产物,旧正常十四份JSON与回执字节保持。
        if not self.failures:
            return
        path = _sidecar(self.receipt)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            payload = {
                "format_version": 1,
                "run_id": self.run_id,
                "receipt_sha256": hashlib.sha256(
                    _read_bounded(self.receipt)
                ).hexdigest(),
                "failures": [
                    {"module": module, "phase": phase}
                    for module, phase in sorted(self.failures)
                ],
            }
            with temporary.open("xb") as stream:
                stream.write((json.dumps(payload, sort_keys=True) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, ValueError):
            # 诊断无验收权威;辅助写入失败不改变原pytest的执行或退出码。
            pass
        finally:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def read_failure_diagnostics(
    root: Path, receipt: Path, run_id: str
) -> tuple[tuple[str, str], ...]:
    """读取前重核对同次回执字节、路径白名单和闭集,坏/缺诊断只返回空。"""
    try:
        path = _sidecar(receipt)
        raw = _read_bounded(receipt)
        record = json.loads(raw)
        document = json.loads(_read_bounded(path))
        if (
            type(record) is not dict
            or record.get("run_id") != run_id
            or type(record.get("format_version")) is not int
            or record["format_version"] != 1
            or type(document) is not dict
            or set(document)
            != {"format_version", "run_id", "receipt_sha256", "failures"}
            or type(document["format_version"]) is not int
            or document["format_version"] != 1
            or document["run_id"] != run_id
            or document["receipt_sha256"] != hashlib.sha256(raw).hexdigest()
            or type(document["failures"]) is not list
        ):
            return ()
        allowed = _modules(root)
        rows = document["failures"]
        if not rows or len(rows) > 4 * len(allowed):
            return ()
        result = []
        for row in rows:
            if (
                type(row) is not dict
                or set(row) != {"module", "phase"}
                or type(row["module"]) is not str
                or row["module"] not in allowed
                or type(row["phase"]) is not str
                or row["phase"] not in _PHASES
            ):
                return ()
            result.append((row["module"], row["phase"]))
        if result != sorted(set(result)):
            return ()
        return tuple(result)
    except (OSError, ValueError, TypeError, RecursionError):
        return ()
