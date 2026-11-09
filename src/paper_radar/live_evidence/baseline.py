"""认证/cache 接收基线的共享 stat 清单算法;从不读取成员正文。"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from paper_radar.live_evidence.ledger import LedgerError

BASELINE_FORMAT = "auth-cache-stat-v1"
MAX_MEMBERS = 4096
MAX_DEPTH = 32


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def metadata_digest(roots: tuple[Path, ...]) -> str:
    """有序根中的相对成员名、类型和 stat 元数据的 UTF-8 规范 JSON SHA-256。

    根顺序由消费方固定;绝对路径不进入清单或异常。只打开目录 fd,拒绝软链/特殊节点。
    本摘要只比较接收基线;当前属主/权限和根隔离仍分别检查。
    """
    rows: list[tuple[int, str, tuple[int, ...]]] = []

    def walk(fd: int, root_index: int, relative: str, depth: int) -> None:
        if depth > MAX_DEPTH or len(rows) >= MAX_MEMBERS:
            raise LedgerError("binding_observation_unavailable")
        before = os.fstat(fd)
        rows.append((root_index, relative, _identity(before)))
        with os.scandir(fd) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            if len(rows) >= MAX_MEMBERS:
                raise LedgerError("binding_observation_unavailable")
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            child_relative = f"{relative}/{name}"
            if stat.S_ISDIR(info.st_mode):
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                try:
                    if _identity(os.fstat(child)) != _identity(info):
                        raise LedgerError("binding_observation_unavailable")
                    walk(child, root_index, child_relative, depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                rows.append((root_index, child_relative, _identity(info)))
                if _identity(
                    os.stat(name, dir_fd=fd, follow_symlinks=False)
                ) != _identity(info):
                    raise LedgerError("binding_observation_unavailable")
            else:
                raise LedgerError("binding_observation_unavailable")
        if _identity(os.fstat(fd)) != _identity(before):
            raise LedgerError("binding_observation_unavailable")

    try:
        if not roots or len(roots) > MAX_MEMBERS:
            raise LedgerError("binding_observation_unavailable")
        for root_index, root in enumerate(roots):
            # O_NOFOLLOW 保护末段;调用方先分别验证固定根与祖先的隔离权限。
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                walk(fd, root_index, ".", 0)
            finally:
                os.close(fd)
    except OSError as error:
        raise LedgerError("binding_observation_unavailable") from error
    data = (
        json.dumps(
            {"format": BASELINE_FORMAT, "members": rows},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    return hashlib.sha256(data).hexdigest()
