"""备份受控路径、全量分段复制和不可覆盖目录发布。"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import stat
from pathlib import Path

from paper_radar.backup.manifest import (
    MANIFEST_FILE,
    BackupError,
    BackupManifest,
    BackupReason,
    FileEntry,
)

CHUNK_SIZE = 1024 * 1024


def file_entry(path: Path, relative: str) -> FileEntry:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return FileEntry(path=relative, sha256=digest.hexdigest(), size_bytes=size)


def controlled_path(root: Path, relative: str) -> Path:
    parts = relative.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise BackupError(BackupReason.UNSAFE_PATH)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise BackupError(BackupReason.UNSAFE_PATH)
    return current


def verify_file(root: Path, entry: FileEntry, *, blob: bool = False) -> None:
    path = controlled_path(root, entry.path)
    try:
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode):
            raise BackupError(BackupReason.FILE_CORRUPT)
        if blob and stat.S_IMODE(mode) != 0o400:
            raise BackupError(BackupReason.FILE_CORRUPT)
        if file_entry(path, entry.path) != entry:
            raise BackupError(BackupReason.FILE_CORRUPT)
    except FileNotFoundError:
        raise BackupError(BackupReason.FILE_MISSING) from None
    except OSError:
        raise BackupError(BackupReason.FILE_CORRUPT) from None


def expected_entries(manifest: BackupManifest) -> set[str]:
    entries = {MANIFEST_FILE, manifest.database.path}
    for blob in manifest.blobs:
        entries.add(blob.path)
        entries.update(
            str(parent) for parent in Path(blob.path).parents if str(parent) != "."
        )
    return entries


def verify_tree(root: Path, manifest: BackupManifest) -> None:
    expected = expected_entries(manifest)
    actual: set[str] = set()
    for path in root.rglob("*"):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            raise BackupError(BackupReason.UNSAFE_PATH)
        if not path.is_file() and not path.is_dir():
            raise BackupError(BackupReason.UNSAFE_PATH)
        if path.is_dir() and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise BackupError(BackupReason.UNSAFE_PATH)
        actual.add(relative)
    if actual - expected:
        raise BackupError(BackupReason.UNEXPECTED_ENTRY)
    if expected - actual:
        raise BackupError(BackupReason.FILE_MISSING)


def mkdir_private(path: Path) -> None:
    if path.is_dir():
        return
    if path.exists() or path.is_symlink():
        raise BackupError(BackupReason.UNSAFE_PATH)
    mkdir_private(path.parent)
    try:
        path.mkdir(mode=0o700)
        sync_directory(path.parent)
    except FileExistsError:
        if not path.is_dir() or path.is_symlink():
            raise BackupError(BackupReason.UNSAFE_PATH) from None


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def copy_file(source: Path, destination: Path, entry: FileEntry, *, mode: int) -> None:
    """复制时再次哈希;不硬链接、不读取完整大对象、不覆盖。"""
    mkdir_private(destination.parent)
    digest = hashlib.sha256()
    size = 0
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_stream:
        while chunk := input_stream.read(CHUNK_SIZE):
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        output.flush()
        os.fchmod(output.fileno(), mode)
        os.fsync(output.fileno())
    if size != entry.size_bytes or digest.hexdigest() != entry.sha256:
        raise BackupError(BackupReason.FILE_CORRUPT)
    sync_directory(destination.parent)


def publish_directory(staging: Path, destination: Path) -> None:
    """原子 rename 且不替换既有空目录;无可靠原语时明确失败。"""
    try:
        rename = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        raise BackupError(BackupReason.PUBLICATION_FAILED) from None
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    # AT_FDCWD=-100; RENAME_NOREPLACE=1,同时保护正常并发和预占位空目录。
    if rename(-100, os.fsencode(staging), -100, os.fsencode(destination), 1) != 0:
        reason = (
            BackupReason.BATCH_EXISTS
            if ctypes.get_errno() in (errno.EEXIST, errno.ENOTEMPTY)
            else BackupReason.PUBLICATION_FAILED
        )
        raise BackupError(reason)
    sync_directory(destination.parent)
