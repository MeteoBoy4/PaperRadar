"""本地安装根、安全解包、完整树身份及不覆盖发布。"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import io
import os
import stat
import tarfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from paper_radar.config.identity import canonical_json
from paper_radar.pi_supply.errors import SupplyError


def no_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise SupplyError("unsafe_path")


def safe_roots(
    database: Path,
    install_root: Path,
    data_root: Path,
    config_root: Path,
    material_root: Path,
) -> Path:
    roots = (install_root, data_root, config_root, material_root)
    for root in roots:
        no_symlink_components(root)
    resolved = tuple(root.resolve() for root in roots)
    for index, root in enumerate(resolved):
        if root == Path("/"):
            raise SupplyError("unsafe_root")
        if index == 0 and database.resolve().is_relative_to(root):
            raise SupplyError("unsafe_root")
        for other in resolved[index + 1 :]:
            if root.is_relative_to(other) or other.is_relative_to(root):
                raise SupplyError("unsafe_root")
    return resolved[0]


def local_filesystem(path: Path) -> None:
    """按 Linux 实际挂载点拒绝网络/未知文件系统,支持范围写入契约。"""
    try:
        candidates = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            fields = line.split()
            split = fields.index("-")
            mount = Path(fields[4].replace("\\040", " ").replace("\\134", "\\"))
            if path.is_relative_to(mount):
                candidates.append((len(mount.parts), fields[split + 1]))
        if not candidates or max(candidates)[1] not in {
            "ext2",
            "ext3",
            "ext4",
            "xfs",
            "btrfs",
            "zfs",
            "tmpfs",
            "overlay",
        }:
            raise SupplyError("filesystem_unsupported")
    except (OSError, ValueError, IndexError):
        raise SupplyError("filesystem_unsupported") from None


def check_space(root: Path) -> None:
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    info = os.statvfs(ancestor)
    if info.f_bavail * info.f_frsize < 512 * 1024 * 1024:
        raise SupplyError("space_insufficient")


def durable_directories(path: Path) -> None:
    """逐级持久化新根及其目录项, 避免只同步树内遗漏根的父目录。"""
    missing = []
    ancestor = path
    while not ancestor.exists():
        missing.append(ancestor)
        ancestor = ancestor.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True, mode=0o700)
        fsync_directory(directory)
        fsync_directory(directory.parent)


def extract_node(raw: bytes, destination: Path, version: str) -> None:
    prefix = f"node-v{version}-linux-x64"
    destination.mkdir()
    links: list[tuple[Path, str, bool]] = []
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:xz") as archive:
            seen: set[str] = set()
            for count, item in enumerate(archive, 1):
                tarfile.data_filter(item, str(destination))
                path = PurePosixPath(item.name)
                if (
                    count > 100000
                    or path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != prefix
                    or item.name in seen
                ):
                    raise SupplyError("archive_unsafe")
                seen.add(item.name)
                relative = Path(*path.parts[1:])
                target = destination / relative
                if relative == Path("."):
                    if not item.isdir():
                        raise SupplyError("archive_unsafe")
                    continue
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif item.isfile():
                    total += item.size
                    if total > 1024 * 1024 * 1024:
                        raise SupplyError("archive_limit")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(item)
                    if source is None:
                        raise SupplyError("archive_unsafe")
                    with target.open("xb") as output:
                        while chunk := source.read(65536):
                            output.write(chunk)
                    target.chmod(0o755 if item.mode & 0o111 else 0o644)
                elif item.issym() or item.islnk():
                    links.append((target, item.linkname, item.islnk()))
                else:
                    raise SupplyError("archive_unsafe")
        for target, value, hard in links:
            target.parent.mkdir(parents=True, exist_ok=True)
            link = PurePosixPath(value)
            if link.is_absolute():
                raise SupplyError("archive_unsafe")
            if hard:
                if not link.parts or link.parts[0] != prefix or ".." in link.parts:
                    raise SupplyError("archive_unsafe")
                source_path = destination.joinpath(*link.parts[1:])
                if not source_path.is_file() or source_path.is_symlink():
                    raise SupplyError("archive_unsafe")
                os.link(source_path, target)
            else:
                target.symlink_to(value)
        tree_hash(destination)
    except (OSError, ValueError, tarfile.TarError):
        raise SupplyError("archive_unsafe") from None


def tree_entries(root: Path) -> Iterator[Path]:
    """完整枚举普通目录,不跟随目录链接且不抑制扫描错误。"""
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                yield path


def tree_hash(root: Path) -> str:
    """tree-v1:排序 POSIX UTF-8 路径,规范 JSON 条目,文件摘要和执行位布尔。"""
    try:
        if root.is_symlink() or not root.is_dir():
            raise SupplyError("tree_invalid")
        rows: list[dict[str, str | bool]] = [
            {
                "path": "",
                "kind": "directory",
                "executable": bool(root.stat().st_mode & 0o111),
            }
        ]
        for path in sorted(
            tree_entries(root), key=lambda p: p.relative_to(root).as_posix()
        ):
            relative = path.relative_to(root).as_posix()
            relative.encode("utf-8", errors="strict")
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                value = os.readlink(path)
                resolved = path.resolve(strict=True)
                if Path(value).is_absolute() or not resolved.is_relative_to(
                    root.resolve()
                ):
                    raise SupplyError("tree_link_unsafe")
                rows.append({"path": relative, "kind": "link", "target": value})
            elif stat.S_ISDIR(mode):
                rows.append(
                    {
                        "path": relative,
                        "kind": "directory",
                        "executable": bool(mode & 0o111),
                    }
                )
            elif stat.S_ISREG(mode):
                digest = hashlib.sha256()
                with path.open("rb") as source:
                    while chunk := source.read(65536):
                        digest.update(chunk)
                rows.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "sha256": digest.hexdigest(),
                        "executable": bool(mode & 0o111),
                    }
                )
            else:
                raise SupplyError("tree_special_file")
        return hashlib.sha256(canonical_json(rows)).hexdigest()
    except (OSError, ValueError, UnicodeError, RuntimeError):
        raise SupplyError("tree_invalid") from None


def freeze_tree(root: Path) -> None:
    for path in tree_entries(root):
        if not path.is_symlink():
            path.chmod(0o555 if path.is_dir() or path.stat().st_mode & 0o111 else 0o444)
    root.chmod(0o555)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_directory(source: Path, destination: Path) -> None:
    """Linux 原子不覆盖发布, 连既有空目录也不替换。"""
    try:
        rename = ctypes.CDLL(None, use_errno=True).renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
            if ctypes.get_errno() in (errno.EEXIST, errno.ENOTEMPTY):
                raise SupplyError("publication_conflict")
            raise SupplyError("publication_failed")
    except AttributeError:
        raise SupplyError("publication_failed") from None


def durable_tree(root: Path) -> None:
    for path in tree_entries(root):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as source:
                os.fsync(source.fileno())
    for path in sorted((p for p in tree_entries(root) if p.is_dir()), reverse=True):
        fsync_directory(path)
    fsync_directory(root)
