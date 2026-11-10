"""项目 resolver 视图公共接缝;只修改当前封装的命名空间。"""

import ctypes
import hashlib
import os
import stat
from pathlib import Path

from paper_radar.pi_execution.errors import ExecutionError


def apply_resolver_view(view: Path, digest: str) -> None:
    """无宿主特权的私有 user/mount ns;封印部署提供 root 所有固定文件。"""
    info = view.stat()
    target = Path("/etc/resolv.conf")
    inherited = os.path.samefile(view, target)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_mode & 0o022
        or (not inherited and info.st_uid != 0)
        or (inherited and os.access(view, os.W_OK))
        or hashlib.sha256(view.read_bytes()).hexdigest() != digest
    ):
        raise ExecutionError("resolver_unavailable")
    if not inherited:
        uid, gid = os.getuid(), os.getgid()
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.unshare(0x10000000 | 0x00020000) != 0:  # NEWUSER | NEWNS
            raise ExecutionError("resolver_unavailable")
        Path("/proc/self/setgroups").write_text("deny")
        Path("/proc/self/uid_map").write_text(f"0 {uid} 1")
        Path("/proc/self/gid_map").write_text(f"0 {gid} 1")
        # Namespace capabilities cannot affect the host; detach mount propagation first.
        if (
            libc.mount(None, b"/", None, 16384 | (1 << 18), None) != 0
            or libc.mount(os.fsencode(view), os.fsencode(target), None, 4096, None) != 0
            or libc.mount(None, os.fsencode(target), None, 4096 | 32 | 1, None) != 0
        ):
            raise ExecutionError("resolver_unavailable")
        # Preserve the unprivileged parent's ability to inspect the already traced exec.
        if libc.prctl(4, 1, 0, 0, 0) != 0:
            raise ExecutionError("resolver_unavailable")
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ExecutionError("resolver_unavailable")
