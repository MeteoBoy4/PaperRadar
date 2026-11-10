"""auth-cache-stat-v2: 固定批准基线的不变量摘要;不读取成员正文。"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from paper_radar.live_evidence.ledger import LedgerError

BASELINE_FORMAT = "auth-cache-stat-v2"
MAX_MEMBERS = 4096
MAX_DEPTH = 32
EVOLVING_MEMBERS = frozenset({".", "./auth.json", "./models-store.json"})


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
    """采集与当前比较共用;仅三个固定名称豁免 inode/size/mtime/ctime。

    所有根与成员仍登记于固定摘要,无自动重定基线。完整 stat 用于本次采样的
    并发复核,豁免不适用于采样过程中的变化。目录链接数按基线比较。
    """
    rows: list[tuple[int, str, tuple[int, ...]]] = []

    def walk(fd: int, root_index: int, relative: str, depth: int) -> None:
        if depth > MAX_DEPTH or len(rows) >= MAX_MEMBERS:
            raise LedgerError("binding_observation_unavailable")
        before = _identity(os.fstat(fd))
        rows.append((root_index, relative, before))
        with os.scandir(fd) as entries:
            names = sorted(entry.name for entry in entries)
        observed: list[tuple[str, tuple[int, ...]]] = []
        for name in names:
            if len(rows) >= MAX_MEMBERS or name == "node-compile-cache":
                raise LedgerError("binding_observation_unavailable")
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            identity = _identity(info)
            observed.append((name, identity))
            child_relative = f"{relative}/{name}"
            if stat.S_ISDIR(info.st_mode):
                # 可演进文件名不能被替换为目录。
                if child_relative in EVOLVING_MEMBERS:
                    raise LedgerError("binding_observation_unavailable")
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                try:
                    if _identity(os.fstat(child)) != identity:
                        raise LedgerError("binding_observation_unavailable")
                    walk(child, root_index, child_relative, depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                rows.append((root_index, child_relative, identity))
            else:
                raise LedgerError("binding_observation_unavailable")
        # 在整棵子树采样后再次核对全部成员,包含获准演进字段。
        for name, identity in observed:
            if _identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != identity:
                raise LedgerError("binding_observation_unavailable")
        if _identity(os.fstat(fd)) != before:
            raise LedgerError("binding_observation_unavailable")

    try:
        if not roots or len(roots) > MAX_MEMBERS:
            raise LedgerError("binding_observation_unavailable")
        for root_index, root in enumerate(roots):
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                before = _identity(os.fstat(fd))
                walk(fd, root_index, ".", 0)
                if _identity(root.lstat()) != before:
                    raise LedgerError("binding_observation_unavailable")
            finally:
                os.close(fd)
    except OSError as error:
        raise LedgerError("binding_observation_unavailable") from error
    invariant_rows = [
        (
            index,
            name,
            tuple(value for i, value in enumerate(identity) if i in (0, 2, 3, 4, 5)),
        )
        if name in EVOLVING_MEMBERS
        else (index, name, identity)
        for index, name, identity in rows
    ]
    data = (
        json.dumps(
            {"format": BASELINE_FORMAT, "members": invariant_rows},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    return hashlib.sha256(data).hexdigest()
