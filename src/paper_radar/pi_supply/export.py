"""只从已核验历史投影固定小型材料;整组预检后不覆盖发布。"""

from __future__ import annotations

import os
import re
import stat
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from paper_radar.pi_supply.errors import SupplyError

MATERIALS = (
    "package.json",
    "package-lock.json",
    "release.json",
    "supply-manifest.json",
    "integrity-supplements.json",
    "SHASUMS256.txt",
)


@dataclass(frozen=True)
class ExportResult:
    supply_id: str
    files: tuple[str, ...]
    created: tuple[str, ...]


def export_evidence_layout(digests: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """完整合法摘要到固定短名的纯映射;相同摘要去重,短名冲突拒绝。"""
    names: dict[str, str] = {}
    for digest in digests:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SupplyError("supply_corrupt")
        name = f"d5-evidence/{digest[:16]}.bin"
        if name in names and names[name] != digest:
            raise SupplyError("export_evidence_collision")
        names[name] = digest
    return tuple((digest, name) for name, digest in sorted(names.items()))


@contextmanager
def _directory(path: Path, *, create: bool = False) -> Iterator[int | None]:
    # Every traversal uses held directory descriptors, so a concurrent path swap
    # cannot redirect a publication into a symlink target.
    path = path.absolute()
    if ".." in path.parts:
        raise SupplyError("unsafe_path")
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            try:
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not create:
                    yield None
                    return
                try:
                    os.mkdir(part, mode=0o755, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _matches(parent: int, name: str, raw: bytes) -> bool:
    try:
        metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(metadata.st_mode):
        raise SupplyError("export_conflict")
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
    )
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise SupplyError("export_conflict")
        if stream.read(len(raw) + 1) != raw:
            raise SupplyError("export_conflict")
    return True


def _publish(parent: int, name: str, raw: bytes) -> bool:
    if _matches(parent, name, raw):
        return False
    temporary = f".pi-export-{uuid.uuid4().hex}"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
        dir_fd=parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(
                temporary,
                name,
                src_dir_fd=parent,
                dst_dir_fd=parent,
                follow_symlinks=False,
            )
        except FileExistsError:
            if not _matches(parent, name, raw):
                raise SupplyError("export_failed") from None
            return False
        os.fsync(parent)
        return True
    finally:
        os.unlink(temporary, dir_fd=parent)
        os.fsync(parent)


def export_supply(database: Path, supply_id: str, target: Path) -> ExportResult:
    from paper_radar.pi_supply.service import show_supply

    record = show_supply(database, supply_id)
    contents = {
        role: record.manifest.canonical_bytes
        if role == "supply-manifest.json"
        else record.materials[role]
        for role in MATERIALS
    }
    digests = (
        evidence.sha256
        for evidence in record.manifest.d5.evidence
        if evidence.kind == "evidence_file" and evidence.sha256 is not None
    )
    for digest, name in export_evidence_layout(digests):
        contents[name] = record.materials[f"d5-evidence/{digest}.bin"]
    directory = target / supply_id
    try:
        if not all(
            hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
        ):
            raise SupplyError("export_failed")
        missing = []
        for name, raw in contents.items():
            path = directory / name
            with _directory(path.parent) as parent:
                if parent is None or not _matches(parent, path.name, raw):
                    missing.append(name)
        created = []
        for name in missing:
            path = directory / name
            with _directory(path.parent, create=True) as parent:
                assert parent is not None
                if _publish(parent, path.name, contents[name]):
                    created.append(name)
        return ExportResult(supply_id, tuple(contents), tuple(created))
    except (OSError, ValueError, NotImplementedError):
        raise SupplyError("export_failed") from None
