"""受控根内路径与目录持久化;不解释制品或备份领域错误。"""

import os
from collections.abc import Callable
from pathlib import Path


class UnsafePathError(ValueError):
    """相对路径穿越或根内符号链接。"""


def controlled_path(
    root: Path,
    relative: str,
    *,
    create_directory: Callable[[Path], None] | None = None,
) -> Path:
    """根由调用者预先解析;可逐级创建父目录,但每个组件先拒绝链接。"""
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise UnsafePathError("内容对象路径不安全")
    current = root
    if create_directory is not None:
        create_directory(current)
    for index, part in enumerate(parts):
        current = current / part
        if current.is_symlink():
            raise UnsafePathError("数据根内不允许符号链接；请检查受控目录")
        if create_directory is not None and index < len(parts) - 1:
            create_directory(current)
    return current


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
