"""真实恢复 CLI 的文件系统屏障与故障,不替换服务或校验器。"""

import os
from typing import Any

from tests.a3_process_support import checkpoint

phase = os.environ.get("A3_RESTORE_PHASE")
original_open = os.open
original_rename = os.rename


def open_file(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
    if (
        ".restore-staging-" in str(path)
        and "/blobs/" in str(path)
        and flags & os.O_CREAT
    ):
        if phase == "copy_fail":
            raise OSError("SECRET copy failure")
        if phase == "copy":
            checkpoint()
    return original_open(path, flags, *args, **kwargs)


def rename(source: Any, destination: Any, *args: Any, **kwargs: Any) -> None:
    if ".restore-staging-" in str(source):
        if phase == "publish_fail":
            raise OSError("SECRET publish failure")
        if phase == "before_publish":
            checkpoint()
    original_rename(source, destination, *args, **kwargs)
    if ".restore-staging-" in str(source) and phase == "after_publish":
        checkpoint()


setattr(os, "open", open_file)  # noqa: B010
setattr(os, "rename", rename)  # noqa: B010
