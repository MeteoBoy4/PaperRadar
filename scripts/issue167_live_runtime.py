"""Offline runtime binding and ordinary-worker-only application import boundary.

The root entry never calls this module's application-importing functions.
Source imports compile the bound source directly; stale/unbound pyc is not used.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import json
import os
import stat
import sys
import sysconfig
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

PROJECT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "alembic",
    "sqlalchemy",
    "greenlet",
    "pydantic",
    "pydantic_core",
    "annotated_types",
    "typing_inspection",
    "typing_extensions.py",
    "yaml",
    "mako",
    "markupsafe",
    "httpx",
    "httpcore",
    "h11",
    "anyio",
    "sniffio",
    "idna",
    "certifi",
    "typer",
    "click",
    "rich",
    "pygments",
    "shellingham",
    "markdown_it",
    "mdurl",
    "packaging",
    "annotated_doc",
)
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


class RuntimeRejected(ValueError):
    """Only fixed categories leave this boundary."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_file(path: Path, limit: int = MAX_FILE) -> bytes:
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise RuntimeRejected("runtime_path_unknown")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise RuntimeRejected("runtime_file_unknown")
        raw = source.read(limit + 1)
        after = os.fstat(source.fileno())
    if len(raw) > limit or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise RuntimeRejected("runtime_file_unknown")
    return raw


def _members(root: Path) -> set[Path]:
    if root.is_symlink():
        raise RuntimeRejected("runtime_path_unknown")
    if root.is_file():
        return {root}
    if not root.is_dir():
        raise RuntimeRejected("runtime_path_unknown")
    result: set[Path] = set()
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name in {
                    "__pycache__",
                    "site-packages",
                    "test",
                    "tests",
                    "sitecustomize.py",
                }:
                    continue
                p = Path(entry.path)
                if entry.name.startswith("config-") and entry.is_dir(
                    follow_symlinks=False
                ):
                    continue
                if entry.is_symlink():
                    if (
                        not p.resolve(strict=True).is_relative_to(root)
                        or not p.resolve().is_file()
                    ):
                        raise RuntimeRejected("runtime_path_unknown")
                    result.add(p)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(p)
                elif entry.is_file(follow_symlinks=False):
                    if not p.name.endswith((".pyc", ".pyo")):
                        result.add(p)
                else:
                    raise RuntimeRejected("runtime_file_unknown")
        if len(result) > 30000:
            raise RuntimeRejected("runtime_limit_unknown")
    return result


def prepare_binding() -> dict[str, Any]:
    """Only public code/dependency bytes; no DB, credentials or executable probe."""
    site = Path(sysconfig.get_path("purelib")).resolve()
    roots = [PROJECT / "src/paper_radar", Path(sysconfig.get_path("stdlib"))]
    roots.extend(site / name for name in PACKAGES if (site / name).exists())
    files = {
        PROJECT / "uv.lock",
        PROJECT / "pyproject.toml",
        Path(sys.executable).resolve(),
    }
    for root in roots:
        files |= _members(root)
    total = 0
    identities = {}
    links = {}
    for path in sorted(files):
        if path.is_symlink():
            links[str(path)] = {
                "target": os.readlink(path),
                "resolved": str(path.resolve(strict=True)),
            }
        raw = read_file(path.resolve(strict=True))
        total += len(raw)
        if total > MAX_TOTAL:
            raise RuntimeRejected("runtime_limit_unknown")
        identities[str(path)] = digest(raw)
    return {
        "kind": "ordinary_worker_bound_application_runtime",
        "uid": os.getuid(),
        "python_version": list(sys.version_info[:3]),
        "python": str(Path(sys.executable).resolve()),
        "source_parent": str(PROJECT / "src"),
        "site_packages": str(site),
        "roots": [str(p) for p in roots],
        "files": identities,
        "links": links,
        "bytecode_policy": "compile_bound_source_no_pyc",
        "logical_database_io": "none",
    }


def _unique_pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        if key in result:
            raise RuntimeRejected("runtime_binding_unknown")
        result[key] = value
    return result


def load_binding(path: Path, *, key: str | None = None) -> dict[str, Any]:
    try:
        x = json.loads(
            read_file(path, 8 * 1024 * 1024), object_pairs_hook=_unique_pairs
        )
        if key is not None:
            if (
                key != "application_runtime"
                or type(x) is not dict
                or set(x)
                != {
                    "kind",
                    "supply",
                    "synthetic_manifest_sha256",
                    "nsswitch_sha256",
                    "hostname_contains_dot",
                    "application_runtime",
                    "auth_input_declaration",
                    "observation_choice",
                }
            ):
                raise RuntimeRejected("runtime_binding_unknown")
            x = x[key]
        if (
            type(x) is not dict
            or set(x)
            != {
                "kind",
                "uid",
                "python_version",
                "python",
                "source_parent",
                "site_packages",
                "roots",
                "files",
                "links",
                "bytecode_policy",
                "logical_database_io",
            }
            or x["kind"] != "ordinary_worker_bound_application_runtime"
            or type(x["uid"]) is not int
            or x["uid"] <= 0
            or x["bytecode_policy"] != "compile_bound_source_no_pyc"
            or x["logical_database_io"] != "none"
            or type(x["files"]) is not dict
            or not x["files"]
            or type(x["links"]) is not dict
            or len(x["files"]) > 30000
            or type(x["roots"]) is not list
            or not x["roots"]
            or type(x["python_version"]) is not list
            or len(x["python_version"]) != 3
            or any(type(v) is not int or v < 0 for v in x["python_version"])
        ):
            raise RuntimeRejected("runtime_binding_unknown")
        for s in [
            x["python"],
            x["source_parent"],
            x["site_packages"],
            *x["roots"],
            *x["files"],
        ]:
            if (
                type(s) is not str
                or not Path(s).is_absolute()
                or ".." in Path(s).parts
                or str(Path(s)) != s
            ):
                raise RuntimeRejected("runtime_binding_unknown")
        for value in x["files"].values():
            if (
                type(value) is not str
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise RuntimeRejected("runtime_binding_unknown")
        for name, link in x["links"].items():
            if (
                name not in x["files"]
                or type(link) is not dict
                or set(link) != {"target", "resolved"}
                or type(link["target"]) is not str
                or type(link["resolved"]) is not str
                or not Path(link["resolved"]).is_absolute()
                or Path(link["target"]).is_absolute()
            ):
                raise RuntimeRejected("runtime_binding_unknown")
        if x["python"] not in x["files"]:
            raise RuntimeRejected("runtime_binding_unknown")
        return cast(dict[str, Any], x)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise RuntimeRejected("runtime_binding_unknown") from None


def verify_binding(binding: dict[str, Any]) -> None:
    if os.getuid() == 0 or os.geteuid() == 0 or os.getuid() != binding["uid"]:
        raise RuntimeRejected("ordinary_worker_required")
    if list(sys.version_info[:3]) != binding["python_version"]:
        raise RuntimeRejected("runtime_python_unknown")
    files = set()
    for root in binding["roots"]:
        files |= {str(p) for p in _members(Path(root))}
    non_roots = {
        s
        for s in binding["files"]
        if not any(Path(s).is_relative_to(Path(r)) for r in binding["roots"])
    }
    if files | non_roots != set(binding["files"]):
        raise RuntimeRejected("runtime_members_changed")
    total = 0
    for name, expected in binding["files"].items():
        raw = bound_bytes(Path(name), binding["links"])
        total += len(raw)
        if total > MAX_TOTAL or digest(raw) != expected:
            raise RuntimeRejected("runtime_member_changed")
    if (
        digest(read_file(Path(sys.executable).resolve()))
        != binding["files"][binding["python"]]
    ):
        raise RuntimeRejected("runtime_python_unknown")


def bound_bytes(path: Path, links: dict[str, Any]) -> bytes:
    if str(path) not in links:
        return read_file(path)
    link = links[str(path)]
    if (
        not path.is_symlink()
        or os.readlink(path) != link["target"]
        or str(path.resolve(strict=True)) != link["resolved"]
    ):
        raise RuntimeRejected("runtime_link_changed")
    return read_file(Path(link["resolved"]))


class BoundSourceLoader(importlib.machinery.SourceFileLoader):
    def __init__(
        self, name: str, path: str, expected: str, links: dict[str, Any] | None = None
    ) -> None:
        super().__init__(name, path)
        self.expected = expected
        self.links = links or {}

    def get_code(self, fullname: str) -> Any:
        raw = bound_bytes(Path(self.path), self.links)
        if digest(raw) != self.expected:
            raise RuntimeRejected("runtime_import_changed")
        return compile(raw, self.path, "exec", dont_inherit=True)


class BoundFinder(importlib.abc.MetaPathFinder):
    def __init__(
        self, files: dict[str, str], links: dict[str, Any] | None = None
    ) -> None:
        self.files = files
        self.links = links or {}

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None:
            spec = importlib.machinery.BuiltinImporter.find_spec(fullname)
            if spec is None:
                spec = importlib.machinery.FrozenImporter.find_spec(fullname)
            if spec is None:
                # Raising here prevents later, unbound meta-path loaders running.
                raise ModuleNotFoundError("runtime_import_unbound", name=fullname)
            return spec
        if spec.origin in {None, "built-in", "frozen"}:
            # A namespace search location must lead to at least one bound member.
            if spec.origin is None and any(
                not any(Path(p).is_relative_to(Path(r)) for p in self.files)
                for r in (spec.submodule_search_locations or ())
            ):
                raise RuntimeRejected("runtime_import_unbound")
            return spec
        origin = str(Path(cast(str, spec.origin)).absolute())
        if (
            origin not in self.files
            or digest(bound_bytes(Path(origin), self.links)) != self.files[origin]
        ):
            raise RuntimeRejected("runtime_import_unbound")
        if origin.endswith(".py"):
            spec.loader = BoundSourceLoader(
                fullname, origin, self.files[origin], self.links
            )
        elif not any(
            origin.endswith(s) for s in importlib.machinery.EXTENSION_SUFFIXES
        ):
            raise RuntimeRejected("runtime_import_unbound")
        return spec


@contextmanager
def application_runtime(binding: dict[str, Any], package_root: Path) -> Iterator[None]:
    verify_binding(binding)
    manifest = json.loads(read_file(package_root / "manifest.json", 65536))
    files = dict(binding["files"])
    files.update(
        {
            str(package_root / n): h
            for n, h in manifest["members"].items()
            if n.endswith(".py")
        }
    )
    finder = BoundFinder(files, binding["links"])
    old_path = list(sys.path)
    sys.path[:0] = [binding["source_parent"], binding["site_packages"]]
    sys.meta_path.insert(0, finder)
    try:
        yield
        verify_binding(binding)
    finally:
        sys.meta_path.remove(finder)
        sys.path[:] = old_path
