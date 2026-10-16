"""离线验收运行前后的代码、工作树与锁文件身份。"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts.offline_evidence import CodeIdentity, file_sha256, git_metadata


@dataclass(frozen=True, slots=True)
class RunIdentity:
    code: CodeIdentity
    lockfile_sha256: str | None
    worktree_sha256: str | None


def _worktree_sha256(root: Path) -> str | None:
    """哈希 Git 管理及非忽略文件的路径、类型和字节; 不保存内容。"""
    try:
        result = subprocess.run(
            ("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"),
            cwd=root,
            capture_output=True,
            check=True,
        )
        digest = hashlib.sha256()
        for relative in sorted(set(result.stdout.split(b"\0")) - {b""}):
            path = root / os.fsdecode(relative)
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            if not os.path.lexists(path):
                digest.update(b"missing\0")
                continue
            digest.update(stat.S_IMODE(path.lstat().st_mode).to_bytes(2, "big"))
            if path.is_symlink():
                digest.update(b"link\0")
                digest.update(os.fsencode(os.readlink(path)))
            elif path.is_file():
                digest.update(b"file\0")
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            else:
                digest.update(b"other\0")
        return digest.hexdigest()
    except (OSError, subprocess.CalledProcessError):
        return None


def capture_identity(root: Path) -> RunIdentity:
    """采集一次运行的 HEAD、工作树与锁文件身份。"""
    return RunIdentity(
        code=git_metadata(root),
        lockfile_sha256=file_sha256(root / "uv.lock"),
        worktree_sha256=_worktree_sha256(root),
    )
