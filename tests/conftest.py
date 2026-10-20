"""仅在用例结束后恢复其 tmp_path 目录写权限,供 pytest 正常回收。"""

import os
import stat
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path

import pytest


@pytest.fixture(name="tmp_path")
def tmp_path_with_writable_teardown(tmp_path: Path) -> Iterator[Path]:
    # 包装原 fixture,静态和动态请求都适用,未使用 tmp_path 的用例不创建目录。
    root_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    original = os.fstat(root_fd)
    try:
        yield tmp_path
    finally:
        # 路径可能已被删除或替换;只处理原目录,不跟随根或树内的符号链接。
        with suppress(OSError):
            current = tmp_path.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino):
                for _, _, _, directory_fd in os.fwalk(
                    ".", dir_fd=root_fd, follow_symlinks=False
                ):
                    with suppress(OSError):
                        mode = os.fstat(directory_fd).st_mode
                        os.fchmod(directory_fd, mode | stat.S_IWUSR)
        os.close(root_fd)
