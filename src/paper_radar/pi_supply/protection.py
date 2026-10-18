"""已发布安装的唯一使用/回收互斥边界;保护由内核 fd 生命周期决定。"""

from __future__ import annotations

import os
import platform
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import select

from paper_radar.config.compile import RuntimeConfigSnapshot
from paper_radar.pi_supply import tables
from paper_radar.pi_supply.errors import SupplyError, SupplyReason
from paper_radar.pi_supply.filesystem import (
    local_filesystem,
    no_symlink_components,
    tree_hash,
)
from paper_radar.pi_supply.materials import object_bytes
from paper_radar.pi_supply.models import (
    Activation,
    InstallInstance,
    SupplyManifest,
    SupplyRecord,
)
from paper_radar.pi_supply.repository import database_engine, read_state
from paper_radar.pi_supply.selection import load_snapshot, match_snapshot


def check_platform(manifest: SupplyManifest) -> None:
    try:
        libc_info = os.confstr("CS_GNU_LIBC_VERSION") or ""
    except (AttributeError, OSError, ValueError):
        raise SupplyError("platform_mismatch") from None
    if (
        platform.system() != "Linux"
        or platform.machine() != manifest.platform.arch
        or libc_info != f"{manifest.platform.libc} {manifest.libc_version}"
    ):
        raise SupplyError("platform_mismatch")


def check_root_marker(database: Path, root: Path, root_id: str) -> None:
    no_symlink_components(root)
    marker = root / ".paper-radar-install-root"
    if not stat.S_ISREG(marker.stat(follow_symlinks=False).st_mode):
        raise SupplyError("root_foreign")
    with database_engine(database) as engine, engine.connect() as connection:
        owner = connection.execute(
            select(tables.database_identity.c.database_id)
        ).scalar_one()
    with marker.open("rb") as source:
        raw = source.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024 or object_bytes(raw) != {
        "database_id": owner,
        "root_id": root_id,
    }:
        raise SupplyError("root_foreign")


def inspect_instance(
    database: Path, record: SupplyRecord, instance: InstallInstance
) -> None:
    """调用方须持实例锁;全树工作在 SQL 写事务之外。"""
    if not instance.path.is_dir():
        raise SupplyError("install_unavailable")
    root = instance.path.parent.parent
    local_filesystem(root)
    check_root_marker(database, root, instance.root_id)
    no_symlink_components(instance.path)
    if tree_hash(instance.path) != record.manifest.expected_tree:
        raise SupplyError("tree_mismatch")
    for entry in (
        record.manifest.node_entry,
        record.manifest.npm_entry,
        record.manifest.pi_entry,
    ):
        target = instance.path / entry
        if not target.is_file() or not target.resolve().is_relative_to(instance.path):
            raise SupplyError("entry_invalid")


@dataclass(frozen=True)
class InstallUse:
    record: SupplyRecord
    instance: InstallInstance
    pass_fds: tuple[int, ...]

    @property
    def install_id(self) -> str:
        return self.instance.install_id

    @property
    def supply_id(self) -> str:
        return self.record.supply_id

    @property
    def node(self) -> Path:
        return self.instance.path / self.record.manifest.node_entry

    @property
    def npm(self) -> Path:
        return self.instance.path / self.record.manifest.npm_entry

    @property
    def pi(self) -> Path:
        return self.instance.path / self.record.manifest.pi_entry

    def recheck(self, database: Path) -> str:
        """排他持有者在执行破坏性操作前重新确认登记、归属与实际树。"""
        record, instance = _registered(database, self.supply_id, self.install_id)
        if (
            record.manifest != self.record.manifest
            or instance.path != self.instance.path
            or instance.root_id != self.instance.root_id
        ):
            raise SupplyError("install_unavailable")
        local_filesystem(instance.path.parent.parent)
        check_root_marker(database, instance.path.parent.parent, instance.root_id)
        no_symlink_components(instance.path)
        if not instance.path.is_dir():
            raise SupplyError("install_unavailable")
        return tree_hash(instance.path)


@dataclass(frozen=True)
class ProtectionObservation:
    state: Literal["in_flight", "idle", "unknown"]
    reason: SupplyReason | None = None


def _registered(
    database: Path, supply_id: str, install_id: str
) -> tuple[SupplyRecord, InstallInstance]:
    for record in read_state(database)[0]:
        if record.supply_id == supply_id:
            for instance in record.installs:
                if instance.install_id == install_id and any(
                    check.passed for check in instance.checks
                ):
                    return record, instance
    raise SupplyError("install_unavailable")


def _open_lock(
    database: Path, root: Path, root_id: str, install_id: str, *, create: bool
) -> int:
    if not re.fullmatch(r"[0-9a-f]{32}", install_id):
        raise SupplyError("unsafe_path")
    local_filesystem(root)
    check_root_marker(database, root, root_id)
    directory = root / ".locks"
    no_symlink_components(directory)
    if create:
        directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise SupplyError("protection_unknown")
    name = f"{install_id}.lock"
    directory_fd = os.open(
        directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_NOFOLLOW
            | os.O_CLOEXEC
            | os.O_NONBLOCK
            | (os.O_CREAT | os.O_RDWR if create else os.O_RDONLY),
            0o600,
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        linked = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.getuid()
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
        ):
            raise SupplyError("protection_unknown")
        return descriptor
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        raise
    finally:
        os.close(directory_fd)


@contextmanager
def _locked(
    database: Path,
    root: Path,
    root_id: str,
    install_id: str,
    *,
    exclusive: bool,
    create: bool,
) -> Iterator[int]:
    try:
        import fcntl
    except ImportError:
        raise SupplyError("filesystem_unsupported") from None

    try:
        descriptor = _open_lock(database, root, root_id, install_id, create=create)
    except OSError:
        raise SupplyError("protection_unknown") from None
    try:
        try:
            fcntl.flock(
                descriptor,
                (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            raise SupplyError("install_busy") from None
        except OSError:
            raise SupplyError("protection_unknown") from None
        yield descriptor
    finally:
        # LOCK_UN would unlock the same OFD still inherited by a live child.
        os.close(descriptor)


@contextmanager
def _acquire(
    database: Path,
    supply_id: str,
    install_id: str,
    *,
    snapshot: RuntimeConfigSnapshot | None = None,
    current: Activation | None = None,
) -> Iterator[InstallUse]:
    _, candidate = _registered(database, supply_id, install_id)
    with _locked(
        database,
        candidate.path.parent.parent,
        candidate.root_id,
        candidate.install_id,
        exclusive=False,
        create=True,
    ) as descriptor:
        record, instance = _registered(database, supply_id, install_id)
        if candidate.path != instance.path or candidate.root_id != instance.root_id:
            raise SupplyError("install_unavailable")
        if current is not None and read_state(database)[2] != current:
            raise SupplyError("selection_changed")
        if snapshot is not None:
            match_snapshot(snapshot, record.manifest.pi_version)
        check_platform(record.manifest)
        inspect_instance(database, record, instance)
        yield InstallUse(record, instance, (descriptor,))


@contextmanager
def acquire_install(
    database: Path, supply_id: str, install_id: str
) -> Iterator[InstallUse]:
    """显式实例:先锁,再重读登记/全树。无等待、无 PID/TTL 推断。"""
    with _acquire(database, supply_id, install_id) as handle:
        yield handle


@contextmanager
def use_install(database: Path, snapshot_reference: str) -> Iterator[InstallUse]:
    """以调用方快照取得当前选择;句柄不再读取可变选择。"""
    snapshot = load_snapshot(database, snapshot_reference)
    current = read_state(database)[2]
    if current is None:
        raise SupplyError("selection_missing")
    with _acquire(
        database,
        current.supply_id,
        current.install_id,
        snapshot=snapshot,
        current=current,
    ) as handle:
        yield handle


@contextmanager
def exclusive_install(
    database: Path, supply_id: str, install_id: str
) -> Iterator[InstallUse]:
    """GC 非阻塞排他取得;保持上下文直到复核/退役/移出可用集合。"""
    _, candidate = _registered(database, supply_id, install_id)
    with _locked(
        database,
        candidate.path.parent.parent,
        candidate.root_id,
        candidate.install_id,
        exclusive=True,
        create=False,
    ) as descriptor:
        record, instance = _registered(database, supply_id, install_id)
        handle = InstallUse(record, instance, (descriptor,))
        handle.recheck(database)
        yield handle


def probe_install(
    database: Path, supply_id: str, install_id: str
) -> ProtectionObservation:
    """独立只读 open 探测现有锁;瞬时 idle 不是未来删除许可。"""
    try:
        _, instance = _registered(database, supply_id, install_id)
        with _locked(
            database,
            instance.path.parent.parent,
            instance.root_id,
            instance.install_id,
            exclusive=True,
            create=False,
        ):
            return ProtectionObservation("idle")
    except SupplyError as error:
        if error.reason == "install_busy":
            return ProtectionObservation("in_flight")
        return ProtectionObservation("unknown", error.reason)


@contextmanager
def publication_protection(
    database: Path, root: Path, root_id: str, install_id: str
) -> Iterator[tuple[int, ...]]:
    """仅供发布路径:实例身份已分配,初始化树外锁并保护发布/复检/短事务。"""
    with _locked(
        database, root, root_id, install_id, exclusive=False, create=True
    ) as descriptor:
        yield (descriptor,)
