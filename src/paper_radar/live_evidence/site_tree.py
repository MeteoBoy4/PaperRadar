"""特权采集的tree-v1读取器;锚定fd且从不跟随文件软链打开内容。"""

import hashlib
import os
import posixpath
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from paper_radar.config.identity import canonical_json


@contextmanager
def _directory(path: Path) -> Iterator[int]:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("tree_observation_untrusted")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in path.parts[1:]:
            child = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


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


def observe_tree(root: Path, *, product_uid: int) -> str:
    """实际文件摘要,不采信DB声明;只读产品拥有的单链接文件,拒绝扫描中漂移。"""
    rows: list[dict[str, str | bool]] = []
    total = 0

    def walk(directory: int, relative: str) -> None:
        nonlocal total
        before = os.fstat(directory)
        if before.st_uid != product_uid or len(rows) >= 250000:
            raise ValueError("tree_observation_untrusted")
        rows.append(
            {
                "path": relative,
                "kind": "directory",
                "executable": bool(before.st_mode & 0o111),
            }
        )
        with os.scandir(directory) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            path = f"{relative}/{name}" if relative else name
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if info.st_uid != product_uid or len(rows) >= 250000:
                raise ValueError("tree_observation_untrusted")
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(name, dir_fd=directory)
                normalized = posixpath.normpath(posixpath.join(relative, target))
                if (
                    target.startswith("/")
                    or normalized == ".."
                    or normalized.startswith("../")
                ):
                    raise ValueError("tree_observation_untrusted")
                # 只核链接目标存在及不逃出安装树;从不打开链接目标内容。
                resolved = (root / path).resolve(strict=True)
                if not resolved.is_relative_to(root):
                    raise ValueError("tree_observation_untrusted")
                rows.append({"path": path, "kind": "link", "target": target})
            elif stat.S_ISDIR(info.st_mode):
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                try:
                    if _identity(os.fstat(child)) != _identity(info):
                        raise ValueError("tree_observation_untrusted")
                    walk(child, path)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                descriptor = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
                )
                digest = hashlib.sha256()
                with os.fdopen(descriptor, "rb") as source:
                    if _identity(os.fstat(source.fileno())) != _identity(info):
                        raise ValueError("tree_observation_untrusted")
                    while chunk := source.read(65536):
                        total += len(chunk)
                        if total > 2 * 1024**3:
                            raise ValueError("tree_observation_untrusted")
                        digest.update(chunk)
                    if _identity(os.fstat(source.fileno())) != _identity(info):
                        raise ValueError("tree_observation_untrusted")
                rows.append(
                    {
                        "path": path,
                        "kind": "file",
                        "sha256": digest.hexdigest(),
                        "executable": bool(info.st_mode & 0o111),
                    }
                )
            else:
                raise ValueError("tree_observation_untrusted")
            if _identity(
                os.stat(name, dir_fd=directory, follow_symlinks=False)
            ) != _identity(info):
                raise ValueError("tree_observation_untrusted")
        if _identity(os.fstat(directory)) != _identity(before):
            raise ValueError("tree_observation_untrusted")

    try:
        with _directory(root) as descriptor:
            walk(descriptor, "")
    except (OSError, UnicodeError, RuntimeError) as error:
        raise ValueError("tree_observation_untrusted") from error
    rows.sort(key=lambda row: str(row["path"]))
    return hashlib.sha256(canonical_json(rows)).hexdigest()
