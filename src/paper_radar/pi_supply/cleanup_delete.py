"""仅删除已持锁并确认身份的实例;目录 fd 固定边界,普通文件从不 chmod。"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.filesystem import (
    fsync_directory,
    no_symlink_components,
    publish_directory,
    tree_hash,
)

DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _open_directory(resources: ExitStack, path: Path) -> int:
    no_symlink_components(path)
    descriptor = os.open(path, DIRECTORY_FLAGS)
    resources.callback(os.close, descriptor)
    if _identity(os.fstat(descriptor)) != _identity(path.lstat()):
        raise SupplyError("cleanup_tree_changed")
    return descriptor


def move_to_trash(path: Path, root: Path, install_id: str, expected: str) -> Path:
    """通过固定目录 fd 不覆盖移动;移动后仍验证同一 inode 与实际树。"""
    no_symlink_components(path)
    no_symlink_components(root)
    trash = root / ".trash"
    no_symlink_components(trash)
    if not trash.exists():
        trash.mkdir(mode=0o700)
        fsync_directory(root)
    target = trash / install_id
    if path == target:
        return path
    with ExitStack() as resources:
        with_directory = _open_directory(resources, path)
        source_parent = _open_directory(resources, path.parent)
        target_parent = _open_directory(resources, trash)
        info = os.fstat(with_directory)
        # Updating '..' when renaming across parents needs write on this directory.
        os.fchmod(with_directory, stat.S_IMODE(info.st_mode) | 0o700)
        parent_info = os.fstat(source_parent)
        os.fchmod(source_parent, stat.S_IMODE(parent_info.st_mode) | 0o700)
        if tree_hash(path) != expected or _identity(path.lstat()) != _identity(info):
            raise SupplyError("cleanup_tree_changed")
        publish_directory(
            Path(f"/proc/self/fd/{source_parent}") / path.name,
            Path(f"/proc/self/fd/{target_parent}") / install_id,
        )
        os.fsync(source_parent)
        os.fsync(target_parent)
        moved = os.stat(install_id, dir_fd=target_parent, follow_symlinks=False)
        if _identity(moved) != _identity(info) or tree_hash(target) != expected:
            raise SupplyError("cleanup_tree_changed")
    return target


def _link_order(links: dict[str, str]) -> list[str]:
    """先删引用者,后删依赖;包括目标路径中间的目录链接。"""
    dependencies: dict[str, set[str]] = {}
    for name, target in links.items():
        queue = [(part, False) for part in reversed((Path(name).parent / target).parts)]
        resolved: list[str] = []
        visited: set[str] = set()
        used = set()
        while queue:
            part, leaving = queue.pop()
            if leaving:
                visited.remove(part)
                continue
            if part in {"", "."}:
                continue
            if part == "..":
                if not resolved:
                    raise SupplyError("tree_link_unsafe")
                resolved.pop()
                continue
            resolved.append(part)
            current = "/".join(resolved)
            if current in links:
                if current in visited:
                    raise SupplyError("tree_link_unsafe")
                visited.add(current)
                used.add(current)
                resolved.pop()
                queue.append((current, True))
                queue.extend(
                    (part, False) for part in reversed(Path(links[current]).parts)
                )
        dependencies[name] = used
    ordered = []
    remaining = set(links)
    while remaining:
        ready = sorted(
            name
            for name in remaining
            if not any(name in dependencies[other] for other in remaining)
        )
        if not ready:
            raise SupplyError("tree_link_unsafe")
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


@contextmanager
def _relative_directory(
    root: int, relative: str, entries: dict[str, os.stat_result]
) -> Iterator[int]:
    """逐组件 nofollow 并核对快照 inode;持有 fd 数量不随包目录数量增长。"""
    descriptor = os.dup(root)
    try:
        prefix = []
        for part in Path(relative).parts:
            prefix.append(part)
            opened = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = opened
            if _identity(os.fstat(descriptor)) != _identity(entries["/".join(prefix)]):
                raise SupplyError("cleanup_tree_changed")
        yield descriptor
    finally:
        os.close(descriptor)


def delete_tree(path: Path, expected: str) -> None:
    """固定目录 inode,不跟随替换链接;链接拓扑删除使每个强杀残留仍满足 tree-v1。"""
    no_symlink_components(path)
    with ExitStack() as resources:
        descriptor = _open_directory(resources, path)
        parent = _open_directory(resources, path.parent)
        entries: dict[str, os.stat_result] = {}
        links: dict[str, str] = {}
        if tree_hash(path) != expected:
            raise SupplyError("cleanup_tree_changed")
        pending = [""]
        while pending:
            relative = pending.pop()
            with _relative_directory(descriptor, relative, entries) as current:
                info = os.fstat(current)
                os.fchmod(current, stat.S_IMODE(info.st_mode) | 0o700)
                for name in os.listdir(current):
                    info = os.stat(name, dir_fd=current, follow_symlinks=False)
                    child = f"{relative}/{name}" if relative else name
                    entries[child] = info
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(child)
                    elif stat.S_ISLNK(info.st_mode):
                        links[child] = os.readlink(name, dir_fd=current)
                    elif not stat.S_ISREG(info.st_mode):
                        raise SupplyError("tree_special_file")
        # All symlinks must disappear while their targets still exist.
        ordered = _link_order(links)
        ordered.extend(
            sorted(name for name, info in entries.items() if stat.S_ISREG(info.st_mode))
        )
        ordered.extend(
            sorted(
                (name for name, info in entries.items() if stat.S_ISDIR(info.st_mode)),
                key=lambda name: (-len(Path(name).parts), name),
            )
        )
        for relative in ordered:
            name = Path(relative).name
            parent_name = Path(relative).parent.as_posix()
            with _relative_directory(
                descriptor, "" if parent_name == "." else parent_name, entries
            ) as parent_fd:
                info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if _identity(info) != _identity(entries[relative]) or stat.S_IFMT(
                    info.st_mode
                ) != stat.S_IFMT(entries[relative].st_mode):
                    raise SupplyError("cleanup_tree_changed")
                if stat.S_ISDIR(info.st_mode):
                    os.rmdir(name, dir_fd=parent_fd)
                else:
                    os.unlink(name, dir_fd=parent_fd)
                os.fsync(parent_fd)
        if _identity(
            os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        ) != _identity(os.fstat(descriptor)):
            raise SupplyError("cleanup_tree_changed")
        os.rmdir(path.name, dir_fd=parent)
        os.fsync(parent)
