"""Narrow diagnostic supply projection; never a product use_install substitute.

Import and load_binding are inert with respect to the bound installation/DB.
Only an ordinary worker may prepare metadata or acquire its existing instance lock.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import re
import sqlite3
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

KIND = "diagnostic_readonly_original_instance_lock_not_product_use_install"
PROJECT = Path(__file__).absolute().parent.parent
KNOWN_DB = PROJECT / ".scratch/exp-2/data/exp2.sqlite3"
KNOWN_ROOT = PROJECT / ".scratch/exp-2/install"
KNOWN_SUPPLY = "50eb56a3a7fab3c1dcdb3c54ea41a8ff1ca808af65182365368e1b3ef06c6587"
KNOWN_INSTALL = "9b8e342f8bb64a29b1b1b0aa51b68c85"
KNOWN_NODE_SHA = "94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90"
MAX_FILE = 256 * 1024 * 1024
MAX_TREE = 2 * 1024 * 1024 * 1024
_IDENTITY_KEYS = {"uid", "gid", "mode", "device", "inode", "nlink"}
_TABLES = {
    "pi_supply_database": {"singleton", "database_id"},
    "pi_install_instances": {"install_id", "supply_id", "root_id"},
    "pi_supply_roots": {"root_id", "path"},
    "pi_supplies": {"supply_id", "manifest"},
    "pi_install_checks": {"install_id", "check_id", "scope", "passed", "reason"},
    "pi_install_retirements": {"install_id"},
    "pi_current_selection": {"singleton", "activation_id"},
    "pi_activation_events": {
        "activation_id",
        "supply_id",
        "install_id",
        "snapshot_id",
        "root_id",
        "root_path",
    },
}


class SupplyRejected(ValueError):
    """Closed diagnostic reason; do not serialize SQLite or OS exception text."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in rows:
        if key in result:
            raise SupplyRejected("supply_binding_unknown")
        result[key] = value
    return result


def _hash(value: object, size: int = 64) -> bool:
    return type(value) is str and re.fullmatch(f"[a-f0-9]{{{size}}}", value) is not None


def _path(value: object) -> Path:
    if type(value) is not str:
        raise SupplyRejected("supply_binding_unknown")
    p = Path(value)
    if not p.is_absolute() or p == Path("/") or ".." in p.parts or str(p) != value:
        raise SupplyRejected("supply_binding_unknown")
    return p


def _no_symlinks(path: Path) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise SupplyRejected("supply_path_unknown")


def _ordinary(uid: int | None = None) -> None:
    if (
        os.getuid() == 0
        or os.geteuid() == 0
        or (uid is not None and os.getuid() != uid)
    ):
        raise SupplyRejected("supply_uid_unknown")


def _identity(path: Path) -> dict[str, int]:
    _no_symlinks(path)
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_mode & 0o022:
        raise SupplyRejected("supply_path_unknown")
    return {
        "uid": s.st_uid,
        "gid": s.st_gid,
        "mode": stat.S_IMODE(s.st_mode),
        "device": s.st_dev,
        "inode": s.st_ino,
        "nlink": s.st_nlink,
    }


def _stamp(s: os.stat_result) -> tuple[int, ...]:
    return (
        s.st_dev,
        s.st_ino,
        s.st_mode,
        s.st_uid,
        s.st_gid,
        s.st_nlink,
        s.st_size,
        s.st_mtime_ns,
        s.st_ctime_ns,
    )


def _open_directory(path: Path) -> int:
    """Traverse each absolute component without following directory symlinks."""
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_file(path: Path) -> int:
    directory = _open_directory(path.parent)
    try:
        return os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=directory,
        )
    finally:
        os.close(directory)


def _read(path: Path, limit: int) -> bytes:
    _no_symlinks(path)
    fd = _open_file(path)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > limit
        ):
            raise SupplyRejected("supply_path_unknown")
        raw = source.read(limit + 1)
        if len(raw) > limit or _stamp(before) != _stamp(os.fstat(source.fileno())):
            raise SupplyRejected("supply_path_unknown")
    return raw


def _hash_file(path: Path, limit: int = MAX_FILE) -> tuple[str, int]:
    _no_symlinks(path)
    fd = _open_file(path)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > limit
        ):
            raise SupplyRejected("supply_tree_unknown")
        digest = hashlib.sha256()
        size = 0
        while chunk := source.read(65536):
            size += len(chunk)
            if size > limit:
                raise SupplyRejected("supply_tree_unknown")
            digest.update(chunk)
        if size != before.st_size or _stamp(before) != _stamp(
            os.fstat(source.fileno())
        ):
            raise SupplyRejected("supply_tree_unknown")
    return digest.hexdigest(), size


def _local_filesystem(path: Path) -> None:
    try:
        candidates = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            fields = line.split()
            split = fields.index("-")
            mount = Path(
                re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields[4])
            )
            if path.is_relative_to(mount):
                candidates.append((len(mount.parts), fields[split + 1]))
        depth = max((level for level, _ in candidates), default=-1)
        kinds = {kind for level, kind in candidates if level == depth}
        if len(kinds) != 1 or not kinds <= {
            "ext2",
            "ext3",
            "ext4",
            "xfs",
            "btrfs",
            "zfs",
            "tmpfs",
            "overlay",
        }:
            raise SupplyRejected("supply_filesystem_unknown")
    except (OSError, ValueError, IndexError):
        raise SupplyRejected("supply_filesystem_unknown") from None


def _authorizer(
    action: int, a: str | None, b: str | None, _db: str | None, _source: str | None
) -> int:
    if action == sqlite3.SQLITE_READ:
        return (
            sqlite3.SQLITE_OK
            if a in _TABLES and b in _TABLES[a]
            else sqlite3.SQLITE_DENY
        )
    if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_TRANSACTION}:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and b in {"json_extract", "public_sha256"}:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


@contextmanager
def _connect(database: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only=ON")

        def public_sha(raw: bytes) -> str:
            if type(raw) is not bytes or len(raw) > 65536:
                raise ValueError("public_manifest_unknown")
            return hashlib.sha256(raw).hexdigest()

        connection.create_function("public_sha256", 1, public_sha, deterministic=True)
        connection.set_authorizer(_authorizer)
        end = time.monotonic() + 5
        connection.set_progress_handler(lambda: int(time.monotonic() >= end), 1000)
        yield connection
    finally:
        connection.close()


def _read_registration(
    database: Path, root: Path, supply_id: str, install_id: str
) -> dict[str, object]:
    try:
        with _connect(database) as con:
            con.row_factory = sqlite3.Row
            con.execute("BEGIN")

            def rows(sql: str, args: tuple[str, ...] = ()) -> list[dict[str, object]]:
                values = [dict(r) for r in con.execute(sql, args).fetchmany(1001)]
                if len(values) > 1000:
                    raise SupplyRejected("supply_registration_unknown")
                return values

            def one(sql: str, args: tuple[str, ...] = ()) -> dict[str, object]:
                result = rows(sql, args)
                if len(result) != 1:
                    raise SupplyRejected("supply_registration_unknown")
                return result[0]

            owner = one("SELECT singleton,database_id FROM pi_supply_database")
            install = one(
                "SELECT i.install_id,i.supply_id,i.root_id,r.path AS root_path "
                "FROM pi_install_instances AS i JOIN pi_supply_roots AS r "
                "ON r.root_id=i.root_id WHERE i.install_id=? AND i.supply_id=?",
                (install_id, supply_id),
            )
            fields = (
                "expected_tree",
                "node_entry",
                "npm_entry",
                "pi_entry",
                "node_version",
                "npm_version",
                "pi_version",
                "libc_version",
                "platform",
            )
            projection = ",".join(
                f"json_extract(CAST(manifest AS TEXT),'$.{name}') AS {name}"
                for name in fields
            )
            manifest = one(
                "SELECT public_sha256(manifest) AS manifest_sha256,"
                + projection
                + " FROM pi_supplies WHERE supply_id=?",
                (supply_id,),
            )
            selected = one(
                "SELECT c.singleton,c.activation_id,a.supply_id,a.install_id,"
                "a.snapshot_id,a.root_id,a.root_path FROM pi_current_selection AS c "
                "JOIN pi_activation_events AS a ON a.activation_id=c.activation_id"
            )
            checks = rows(
                "SELECT check_id,scope,passed,CASE "
                "WHEN passed=1 AND reason='passed' THEN 'passed' "
                "WHEN passed=0 THEN 'recorded_failure' ELSE 'unknown' END "
                "AS reason_category FROM pi_install_checks "
                "WHERE install_id=? ORDER BY check_id",
                (install_id,),
            )
            retired = rows(
                "SELECT install_id FROM pi_install_retirements WHERE install_id=?",
                (install_id,),
            )
            con.rollback()
        if (
            owner["singleton"] != 1
            or not _hash(owner["database_id"], 32)
            or install["root_path"] != str(root)
            or not _hash(install["root_id"], 32)
            or manifest["manifest_sha256"] != supply_id
            or retired
            or selected["singleton"] != 1
            or type(selected["activation_id"]) is not int
            or selected["activation_id"] < 1
            or any(
                selected[k] != install[k]
                for k in ("supply_id", "install_id", "root_id", "root_path")
            )
            or not _hash(selected["snapshot_id"])
            or not checks
            or not any(
                c["passed"] == 1
                and c["scope"] == "install_check"
                and c["reason_category"] == "passed"
                for c in checks
            )
        ):
            raise SupplyRejected("supply_registration_unknown")
        for check in checks:
            if (
                type(check["check_id"]) is not int
                or check["check_id"] < 1
                or type(check["passed"]) is not int
                or check["passed"] not in (0, 1)
                or check["scope"] != "install_check"
                or check["reason_category"]
                != ("passed" if check["passed"] == 1 else "recorded_failure")
            ):
                raise SupplyRejected("supply_registration_unknown")
        manifest["platform"] = json.loads(
            cast(str, manifest["platform"]), object_pairs_hook=_pairs
        )
        result = {
            "database_id": owner["database_id"],
            "root_id": install["root_id"],
            "activation_id": selected["activation_id"],
            "snapshot_id": selected["snapshot_id"],
            "checks": checks,
            **manifest,
        }
        _validate_registration(result)
        return result
    except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
        raise SupplyRejected("supply_registration_unknown") from None


def _validate_registration(r: dict[str, object]) -> None:
    if (
        set(r)
        != {
            "database_id",
            "root_id",
            "activation_id",
            "snapshot_id",
            "checks",
            "manifest_sha256",
            "expected_tree",
            "node_entry",
            "npm_entry",
            "pi_entry",
            "node_version",
            "npm_version",
            "pi_version",
            "libc_version",
            "platform",
        }
        or any(not _hash(r[k], 32) for k in ("database_id", "root_id"))
        or any(
            not _hash(r[k]) for k in ("snapshot_id", "manifest_sha256", "expected_tree")
        )
        or type(r["activation_id"]) is not int
        or r["activation_id"] < 1
        or r["platform"] != {"os": "linux", "arch": "x86_64", "libc": "glibc"}
        or any(
            type(r[k]) is not str
            or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", cast(str, r[k])) is None
            for k in ("node_version", "npm_version", "pi_version")
        )
        or type(r["libc_version"]) is not str
        or re.fullmatch(r"[0-9]+\.[0-9]+", r["libc_version"]) is None
        or r["node_entry"] != "node/bin/node"
        or r["npm_entry"] != "node/lib/node_modules/npm/bin/npm-cli.js"
        or type(r["pi_entry"]) is not str
        or not r["pi_entry"].startswith(
            "app/node_modules/@earendil-works/pi-coding-agent/"
        )
        or ".." in Path(r["pi_entry"]).parts
        or type(r["checks"]) is not list
        or not r["checks"]
    ):
        raise SupplyRejected("supply_binding_unknown")
    for c in cast(list[object], r["checks"]):
        if (
            type(c) is not dict
            or set(c) != {"check_id", "scope", "passed", "reason_category"}
            or type(c["check_id"]) is not int
            or c["check_id"] < 1
            or type(c["passed"]) is not int
            or c["passed"] not in (0, 1)
            or c["scope"] != "install_check"
            or c["reason_category"]
            != ("passed" if c["passed"] == 1 else "recorded_failure")
        ):
            raise SupplyRejected("supply_binding_unknown")
    checks = cast(list[dict[str, object]], r["checks"])
    ids = [c["check_id"] for c in checks]
    if (
        len(checks) > 1000
        or ids != sorted(set(cast(list[int], ids)))
        or not any(c["passed"] == 1 for c in checks)
    ):
        raise SupplyRejected("supply_binding_unknown")


def validate_binding(value: object) -> dict[str, object]:
    try:
        if type(value) is not dict or set(value) != {
            "kind",
            "uid",
            "gid",
            "database",
            "root",
            "supply_id",
            "install_id",
            "install",
            "node",
            "node_sha256",
            "marker_sha256",
            "database_file",
            "lock",
            "registration",
            "whole_tree_checked_during_prepare",
        }:
            raise SupplyRejected("supply_binding_unknown")
        b = cast(dict[str, object], value)
        if (
            b["kind"] != KIND
            or b["whole_tree_checked_during_prepare"] is not False
            or any(
                type(b[k]) is not int or cast(int, b[k]) <= 0 for k in ("uid", "gid")
            )
            or not _hash(b["supply_id"])
            or not _hash(b["install_id"], 32)
            or not _hash(b["node_sha256"])
            or not _hash(b["marker_sha256"])
        ):
            raise SupplyRejected("supply_binding_unknown")
        root = _path(b["root"])
        _path(b["database"])
        install = root / cast(str, b["supply_id"]) / cast(str, b["install_id"])
        if (
            _path(b["install"]) != install
            or _path(b["node"]) != install / "node/bin/node"
        ):
            raise SupplyRejected("supply_binding_unknown")
        for key in ("database_file", "lock"):
            metadata = b[key]
            expected = _IDENTITY_KEYS | ({"path"} if key == "lock" else set())
            if (
                type(metadata) is not dict
                or set(metadata) != expected
                or any(
                    type(metadata[k]) is not int or metadata[k] < 0
                    for k in _IDENTITY_KEYS
                )
                or metadata["uid"] != b["uid"]
                or metadata["nlink"] != 1
                or metadata["mode"] & 0o022
                or metadata["inode"] < 1
            ):
                raise SupplyRejected("supply_binding_unknown")
            if key == "lock" and (
                metadata["mode"] != 0o600
                or _path(metadata["path"])
                != root / ".locks" / f"{b['install_id']}.lock"
            ):
                raise SupplyRejected("supply_binding_unknown")
        if type(b["registration"]) is not dict:
            raise SupplyRejected("supply_binding_unknown")
        _validate_registration(b["registration"])
        if b["registration"]["manifest_sha256"] != b["supply_id"]:
            raise SupplyRejected("supply_binding_unknown")
        return cast(dict[str, object], json.loads(_canonical(b)))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise SupplyRejected("supply_binding_unknown") from None


def load_binding(path: Path) -> dict[str, object]:
    try:
        _identity(path)
        return validate_binding(
            json.loads(_read(path, 65536), object_pairs_hook=_pairs)
        )
    except (OSError, UnicodeError, ValueError):
        raise SupplyRejected("supply_binding_unknown") from None


def prepare_binding(
    database: Path = KNOWN_DB,
    root: Path = KNOWN_ROOT,
    supply_id: str = KNOWN_SUPPLY,
    install_id: str = KNOWN_INSTALL,
) -> dict[str, object]:
    _ordinary()
    database, root = _path(str(database)), _path(str(root))
    if not _hash(supply_id) or not _hash(install_id, 32):
        raise SupplyRejected("supply_binding_unknown")
    try:
        _no_symlinks(root)
        _local_filesystem(root)
        database_file = _identity(database)
        registration = _read_registration(database, root, supply_id, install_id)
        marker = root / ".paper-radar-install-root"
        marker_info = _identity(marker)
        raw = _read(marker, 4096)
        if marker_info["uid"] != os.getuid() or json.loads(
            raw, object_pairs_hook=_pairs
        ) != {
            "database_id": registration["database_id"],
            "root_id": registration["root_id"],
        }:
            raise SupplyRejected("supply_marker_unknown")
        install = root / supply_id / install_id
        node = install / "node/bin/node"
        _identity(node)
        node_sha, _ = _hash_file(node)
        if (
            supply_id == KNOWN_SUPPLY
            and install_id == KNOWN_INSTALL
            and node_sha != KNOWN_NODE_SHA
        ):
            raise SupplyRejected("supply_node_identity_unknown")
        lock_path = root / ".locks" / f"{install_id}.lock"
        try:
            for directory in (root, lock_path.parent):
                _no_symlinks(directory)
                info = directory.lstat()
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o022
                ):
                    raise SupplyRejected("supply_lock_unknown")
            lock = {"path": str(lock_path), **_identity(lock_path)}
        except (OSError, SupplyRejected):
            raise SupplyRejected("supply_lock_unknown") from None
        result = {
            "kind": KIND,
            "uid": os.getuid(),
            "gid": os.getgid(),
            "database": str(database),
            "root": str(root),
            "supply_id": supply_id,
            "install_id": install_id,
            "install": str(install),
            "node": str(node),
            "node_sha256": node_sha,
            "marker_sha256": hashlib.sha256(raw).hexdigest(),
            "database_file": database_file,
            "lock": lock,
            "registration": registration,
            "whole_tree_checked_during_prepare": False,
        }
        return validate_binding(result)
    except SupplyRejected:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise SupplyRejected("supply_registration_unknown") from None


def _tree_hash(root: Path) -> str:
    try:
        _no_symlinks(root)
        if not root.is_dir():
            raise SupplyRejected("supply_tree_unknown")
        root_before = root.lstat()
        pending = [root]
        paths = []
        directories = []
        while pending:
            directory = pending.pop()
            _no_symlinks(directory)
            directory_fd = _open_directory(directory)
            try:
                before = os.fstat(directory_fd)
                directories.append((directory, _stamp(before)))
                with os.scandir(directory_fd) as entries:
                    for entry in entries:
                        path = directory / entry.name
                        paths.append(path)
                        if len(paths) > 100000:
                            raise SupplyRejected("supply_tree_unknown")
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(path)
                if _stamp(before) != _stamp(os.fstat(directory_fd)):
                    raise SupplyRejected("supply_tree_unknown")
            finally:
                os.close(directory_fd)
        rows: list[dict[str, object]] = [
            {
                "path": "",
                "kind": "directory",
                "executable": bool(root_before.st_mode & 0o111),
            }
        ]
        total = 0
        for p in sorted(paths, key=lambda x: x.relative_to(root).as_posix()):
            relative = p.relative_to(root).as_posix()
            relative.encode("utf-8", errors="strict")
            before = p.lstat()
            if stat.S_ISLNK(before.st_mode):
                target = os.readlink(p)
                lexical = Path(os.path.normpath(str(p.parent / target)))
                if Path(target).is_absolute() or not lexical.is_relative_to(root):
                    raise SupplyRejected("supply_tree_unknown")
                if not p.resolve(strict=True).is_relative_to(root):
                    raise SupplyRejected("supply_tree_unknown")
                if _stamp(before) != _stamp(p.lstat()):
                    raise SupplyRejected("supply_tree_unknown")
                rows.append({"path": relative, "kind": "link", "target": target})
            elif stat.S_ISDIR(before.st_mode):
                _no_symlinks(p)
                rows.append(
                    {
                        "path": relative,
                        "kind": "directory",
                        "executable": bool(before.st_mode & 0o111),
                    }
                )
            elif stat.S_ISREG(before.st_mode):
                digest, size = _hash_file(p)
                total += size
                if total > MAX_TREE:
                    raise SupplyRejected("supply_tree_unknown")
                rows.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "sha256": digest,
                        "executable": bool(before.st_mode & 0o111),
                    }
                )
            else:
                raise SupplyRejected("supply_tree_unknown")
        if _stamp(root_before) != _stamp(root.lstat()):
            raise SupplyRejected("supply_tree_unknown")
        if any(_stamp(path.lstat()) != stamp for path, stamp in directories):
            raise SupplyRejected("supply_tree_unknown")
        return hashlib.sha256(_canonical(rows)).hexdigest()
    except (OSError, ValueError, RuntimeError):
        raise SupplyRejected("supply_tree_unknown") from None


@dataclass(frozen=True)
class DiagnosticUse:
    node: Path
    install: Path
    pass_fds: tuple[int, ...]
    identity_metadata: dict[str, object]


def _recheck(b: dict[str, object]) -> None:
    actual = prepare_binding(
        _path(b["database"]),
        _path(b["root"]),
        cast(str, b["supply_id"]),
        cast(str, b["install_id"]),
    )
    if _canonical(actual) != _canonical(b):
        raise SupplyRejected("supply_binding_drift")
    registration = cast(dict[str, object], b["registration"])
    if (
        platform.system() != "Linux"
        or platform.machine() != "x86_64"
        or os.confstr("CS_GNU_LIBC_VERSION") != f"glibc {registration['libc_version']}"
    ):
        raise SupplyRejected("supply_platform_unknown")
    if _tree_hash(_path(b["install"])) != registration["expected_tree"]:
        raise SupplyRejected("supply_tree_mismatch")
    for key in ("node_entry", "npm_entry", "pi_entry"):
        p = _path(b["install"]) / cast(str, registration[key])
        if not p.is_file() or not p.resolve(strict=True).is_relative_to(
            _path(b["install"])
        ):
            raise SupplyRejected("supply_entry_unknown")


@contextmanager
def supply_use(binding: dict[str, object]) -> Iterator[DiagnosticUse]:
    b = validate_binding(binding)
    _ordinary(cast(int, b["uid"]))
    if os.getgid() != b["gid"]:
        raise SupplyRejected("supply_uid_unknown")
    lock = cast(dict[str, object], b["lock"])
    path = _path(lock["path"])
    descriptor = -1
    try:
        try:
            if _identity(path) != {k: lock[k] for k in _IDENTITY_KEYS}:
                raise SupplyRejected("supply_lock_unknown")
            descriptor = _open_file(path)
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != b["uid"]
                or opened.st_nlink != 1
                or stat.S_IMODE(opened.st_mode) != 0o600
                or (opened.st_dev, opened.st_ino) != (lock["device"], lock["inode"])
            ):
                raise SupplyRejected("supply_lock_unknown")
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
            if _identity(path) != {k: lock[k] for k in _IDENTITY_KEYS}:
                raise SupplyRejected("supply_lock_unknown")
        except BlockingIOError:
            raise SupplyRejected("supply_install_busy") from None
        except (OSError, SupplyRejected):
            raise SupplyRejected("supply_lock_unknown") from None
        _recheck(b)
        metadata = {
            "kind": KIND,
            "supply_id": b["supply_id"],
            "install_id": b["install_id"],
            "node_sha256": b["node_sha256"],
            "lock_device": lock["device"],
            "lock_inode": lock["inode"],
            "whole_tree_checked_under_lock": True,
            "product_use_install_assessed": False,
        }
        try:
            yield DiagnosticUse(
                _path(b["node"]), _path(b["install"]), (descriptor,), metadata
            )
        finally:
            _recheck(b)
    finally:
        if descriptor >= 0:
            # No LOCK_UN: live children retain this exact open file description.
            os.close(descriptor)
