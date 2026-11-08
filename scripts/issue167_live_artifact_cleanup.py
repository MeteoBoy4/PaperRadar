"""Owner-invoked, sealed removal of one completed run's retained artifacts.

No application imports, service changes, DB operations, probes, or file-body
inspection of arbitrary descendants. This is an unbound offline H1 helper.
"""

from __future__ import annotations

import hashlib
import json
import os
import resource
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RUN = "e93f7b82c461"
CODE = Path("/home/paperradar-probes/issue167-" + RUN)
RUNTIME = Path("/run/paperradar-issue167-" + RUN)
LEDGER = Path("/var/lib/paperradar/probe-runs/issue167-" + RUN + ".json")
UNIT = "paperradar-167-h1net-" + RUN + ".service"
TABLE = "paperradar167_" + RUN
CGROUP = Path("/sys/fs/cgroup/system.slice") / UNIT
CORE_SHA = "84c75ad3e4ed33a8647afcbd8579c1646cd97031e4d59d4e162fdb835dc766d6"
LEDGER_SHA = "4b947402613b75a6fe326b14c5858945b5ef777ada76fe9c4246dc5dc3c4e9d3"
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


class CleanupRejected(ValueError):
    """Closed reason; never propagate host exception text or file content."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(info: os.stat_result) -> list[int]:
    return [
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_uid,
        info.st_gid,
        stat.S_IMODE(info.st_mode),
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ]


def protected(path: Path, *, uid: int = 0) -> None:
    for part in (path, *path.parents):
        info = part.lstat()
        if info.st_uid != uid or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise CleanupRejected("root_protection_unknown")


def record(
    path: Path,
    *,
    uid: int,
    mode: int,
    limit: int = 33554432,
    dir_fd: int | None = None,
    expected_identity: list[int] | None = None,
) -> bytes:
    fd = os.open(path, FILE_FLAGS, dir_fd=dir_fd)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != uid
            or stat.S_IMODE(before.st_mode) != mode
            or before.st_nlink != 1
            or before.st_size > limit
            or (expected_identity is not None and identity(before) != expected_identity)
        ):
            raise CleanupRejected("record_metadata_unknown")
        chunks = []
        total = 0
        while chunk := os.read(fd, min(65536, limit + 1 - total)):
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                raise CleanupRejected("record_size_unknown")
        if identity(before) != identity(os.fstat(fd)):
            raise CleanupRejected("record_changed")
        return b"".join(chunks)
    finally:
        os.close(fd)


@dataclass
class Tree:
    """Pinned directory descriptors; unlink stays inside the inspected tree."""

    path: Path
    expected: dict[str, list[int]]
    root_uid: int
    worker_uid: int | None = None

    def __post_init__(self) -> None:
        self.fds: dict[str, int] = {}
        self.seen: dict[str, list[int]] = {}

    def _allowed(self, relative: str, info: os.stat_result, device: int) -> None:
        worker = relative == "worker" or relative.startswith("worker/")
        owner = self.worker_uid if worker else self.root_uid
        if (
            info.st_dev != device
            or info.st_uid != owner
            or info.st_gid != owner
            or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
            or info.st_mode & 0o022
            or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
            or stat.S_IMODE(info.st_mode) & 0o7000
        ):
            raise CleanupRejected("tree_boundary_unknown")

    def inspect(self) -> None:
        if self.fds:
            raise CleanupRejected("tree_already_open")
        try:
            self.fds[""] = os.open(self.path, DIR_FLAGS)
            root = os.fstat(self.fds[""])
            self._allowed("", root, self.expected[""][0])
            self.seen[""] = identity(root)
            pending = [""]
            while pending:
                relative = pending.pop()
                fd = self.fds[relative]
                for name in os.listdir(fd):
                    child = relative + "/" + name if relative else name
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    self._allowed(child, info, root.st_dev)
                    self.seen[child] = identity(info)
                    if stat.S_ISDIR(info.st_mode):
                        child_fd = os.open(name, DIR_FLAGS, dir_fd=fd)
                        self.fds[child] = child_fd
                        if identity(os.fstat(child_fd)) != identity(info):
                            raise CleanupRejected("tree_changed")
                        pending.append(child)
            if self.seen != self.expected:
                raise CleanupRejected("tree_inventory_changed")
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self) -> None:
        for relative, expected in self.expected.items():
            if relative:
                parent, _, name = relative.rpartition("/")
                info = os.stat(name, dir_fd=self.fds[parent], follow_symlinks=False)
            else:
                info = self.path.lstat()
            if identity(info) != expected:
                raise CleanupRejected("tree_changed")
        for relative, fd in self.fds.items():
            children = {
                key.rpartition("/")[2]
                for key in self.expected
                if key and key.rpartition("/")[0] == relative
            }
            if set(os.listdir(fd)) != children:
                raise CleanupRejected("tree_changed")

    def read_metadata(self, relative: str, *, uid: int, mode: int) -> bytes:
        self.verify()
        parent, _, name = relative.rpartition("/")
        if relative not in self.expected or parent not in self.fds:
            raise CleanupRejected("runtime_record_unbound")
        fd = self.fds[parent]
        before = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if identity(before) != self.expected[relative]:
            raise CleanupRejected("runtime_record_changed")
        raw = record(
            Path(name),
            uid=uid,
            mode=mode,
            dir_fd=fd,
            expected_identity=self.expected[relative],
        )
        if identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != identity(
            before
        ):
            raise CleanupRejected("runtime_record_changed")
        return raw

    def remove(self) -> int:
        # Never follow descendant paths. A replacement hardlink/symlink can only
        # lose its name inside a pinned owned directory; no target is opened.
        removed = 0
        for relative in sorted(self.expected, key=lambda s: (-s.count("/"), s)):
            if not relative:
                continue
            parent, _, name = relative.rpartition("/")
            fd = self.fds[parent]
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            expected = self.expected[relative]
            actual = identity(before)
            # Removing children legitimately changes directory size/timestamps/
            # link count; its device, inode, type, owner, group and mode stay.
            if (actual[:6] != expected[:6]) or (
                not stat.S_ISDIR(before.st_mode) and actual != expected
            ):
                raise CleanupRejected("tree_changed_during_removal")
            if stat.S_ISDIR(before.st_mode):
                os.rmdir(name, dir_fd=fd)
            else:
                os.unlink(name, dir_fd=fd)
            removed += 1
        before = self.path.lstat()
        if identity(before)[:6] != self.expected[""][:6]:
            raise CleanupRejected("tree_changed_during_removal")
        parent_fd = os.open(self.path.parent, DIR_FLAGS)
        try:
            os.rmdir(self.path.name, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
        return removed + 1

    def close(self) -> None:
        for fd in self.fds.values():
            os.close(fd)
        self.fds.clear()


def mount_roots(raw: str) -> set[Path]:
    points = set()
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) < 10 or "-" not in fields:
            raise CleanupRejected("mount_state_unknown")
        value = fields[4]
        for old, new in (
            (r"\040", " "),
            (r"\011", "\t"),
            (r"\012", "\n"),
            (r"\134", "\\"),
        ):
            value = value.replace(old, new)
        if not value.startswith("/"):
            raise CleanupRejected("mount_state_unknown")
        points.add(Path(value))
    if not points:
        raise CleanupRejected("mount_state_unknown")
    return points


def check_mounts(roots: tuple[Path, ...], points: set[Path]) -> None:
    if any(point.is_relative_to(root) for point in points for root in roots):
        raise CleanupRejected("artifact_mount_unknown")


def verify_host(unit: str, state: bytes, tables: bytes, cgroup: Path) -> None:
    try:
        lines = state.decode("ascii").splitlines()
        pairs = [line.split("=", 1) for line in lines]
        values = dict(pairs)
        expected = {
            "Id": unit,
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "SubState": "dead",
            "MainPID": "0",
            "ControlGroup": "",
            "FragmentPath": "",
            "DropInPaths": "",
        }
        if values != expected or len(pairs) != len(expected):
            raise CleanupRejected("unit_not_absent")
        table_list = json.loads(tables)["nftables"]
        if not isinstance(table_list, list):
            raise ValueError
        for entry in table_list:
            if not isinstance(entry, dict) or len(entry) != 1:
                raise ValueError
            if "metainfo" in entry:
                continue
            value = entry.get("table")
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("family"), str)
                or not isinstance(value.get("name"), str)
            ):
                raise ValueError
            if value["family"] == "inet" and value["name"] == TABLE:
                raise CleanupRejected("table_still_present")
        if os.path.lexists(cgroup):
            raise CleanupRejected("cgroup_not_absent")
    except (ValueError, KeyError, TypeError, UnicodeError) as error:
        if isinstance(error, CleanupRejected):
            raise
        raise CleanupRejected("host_state_unknown") from None


def perform(
    trees: tuple[Tree, ...],
    verify: Callable[[], None],
    progress: dict[str, str],
) -> dict[str, object]:
    try:
        progress["stage"] = "inspect"
        verify()
        for tree in trees:
            tree.inspect()
        # No mutation until every target has passed both passes.
        progress["stage"] = "recheck"
        verify()
        for tree in trees:
            tree.verify()
        progress["stage"] = "remove"
        count = sum(tree.remove() for tree in trees)
        progress["stage"] = "final_check"
        verify()
        if any(os.path.lexists(tree.path) for tree in trees):
            raise CleanupRejected("artifacts_still_present")
        return {
            "scope": "fixed_live_six_retained_artifact_cleanup_only",
            "run_id": RUN,
            "cleanup_result": "code_runtime_removed",
            "original_experiment_result": "unknown",
            "original_ledger_unchanged": True,
            "removed_members_including_roots": count,
            "auth_model_reexecs": 0,
            "network_operations": 0,
            "database_operations": 0,
            "service_mutations": 0,
            "nft_mutations": 0,
            "budget_refund": 0,
        }
    finally:
        for tree in trees:
            tree.close()


def command(tool: str, args: list[str]) -> bytes:
    result = subprocess.run(
        [tool, *args],
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=20,
        check=False,
    )
    if result.returncode or len(result.stdout) > 1048576:
        raise CleanupRejected("readonly_command_unknown")
    return result.stdout


def main(config: dict[str, Any]) -> int:
    progress = {"stage": "initial"}
    try:
        if os.geteuid() != 0:
            raise CleanupRejected("owner_root_required")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if (
            config["run_id"] != RUN
            or config["paths"] != [str(CODE), str(RUNTIME), str(LEDGER)]
            or config["core_sha256"] != CORE_SHA
            or config["ledger_sha256"] != LEDGER_SHA
        ):
            raise CleanupRejected("fixed_scope_changed")
        for path in (CODE, RUNTIME, LEDGER):
            protected(path)
        interpreter = Path(sys.executable).resolve(strict=True)
        protected(interpreter)
        if (
            str(interpreter) != config["bootstrap_python"]["path"]
            or sha(
                record(
                    interpreter,
                    uid=0,
                    mode=stat.S_IMODE(interpreter.lstat().st_mode),
                )
            )
            != config["bootstrap_python"]["sha256"]
        ):
            raise CleanupRejected("bootstrap_python_changed")
        manifest_raw = record(CODE / "manifest.json", uid=0, mode=0o644)
        if sha(manifest_raw) != CORE_SHA:
            raise CleanupRejected("approved_core_changed")
        manifest = json.loads(manifest_raw)
        if len(manifest["members"]) != 40 or set(os.listdir(CODE)) != set(
            manifest["members"]
        ) | {"manifest.json"}:
            raise CleanupRejected("approved_members_changed")
        for name, expected in manifest["members"].items():
            if (
                not isinstance(name, str)
                or Path(name).name != name
                or name in {".", ".."}
            ):
                raise CleanupRejected("approved_member_name_unknown")
            path = CODE / name
            protected(path)
            if (
                sha(record(path, uid=0, mode=stat.S_IMODE(path.lstat().st_mode)))
                != expected
            ):
                raise CleanupRejected("approved_source_changed")
        for tool in manifest["tools"].values():
            path = Path(tool["path"]).resolve(strict=True)
            protected(path)
            if (
                sha(record(path, uid=0, mode=stat.S_IMODE(path.lstat().st_mode)))
                != tool["sha256"]
            ):
                raise CleanupRejected("approved_tool_changed")

        trees = (
            Tree(RUNTIME, config["runtime_inventory"], 0, 1000),
            Tree(CODE, config["code_inventory"], 0),
        )

        def verify() -> None:
            protected(LEDGER)
            if identity(LEDGER.lstat()) != config["ledger_identity"]:
                raise CleanupRejected("original_ledger_metadata_changed")
            raw = record(LEDGER, uid=0, mode=0o600)
            if sha(raw) != LEDGER_SHA:
                raise CleanupRejected("original_ledger_changed")
            original = json.loads(raw)
            if (
                original["run_id"] != RUN
                or original["result"] != "unknown"
                or original["failure_stage"] != "exit"
                or original["restoration_stage"] != "complete"
                or original["restoration"] != config["restoration"]
                or original["database_selection_restoration"]
                != config["database_selection_restoration"]
            ):
                raise CleanupRejected("original_restoration_unknown")
            systemctl = manifest["tools"]["systemctl"]["path"]
            nft = manifest["tools"]["nft"]["path"]
            state = command(
                systemctl,
                [
                    "show",
                    UNIT,
                    "--property=Id,LoadState,ActiveState,SubState,MainPID,ControlGroup,FragmentPath,DropInPaths",
                    "--no-pager",
                ],
            )
            tables = command(nft, ["-j", "list", "tables"])
            verify_host(UNIT, state, tables, CGROUP)
            for path in (
                Path("/etc/systemd/system") / UNIT,
                Path("/run/systemd/system") / UNIT,
            ):
                if os.path.lexists(path) or os.path.lexists(Path(str(path) + ".d")):
                    raise CleanupRejected("unit_file_not_absent")
            check_mounts(
                (CODE, RUNTIME), mount_roots(Path("/proc/self/mountinfo").read_text())
            )
            if progress["stage"] == "recheck":
                # Both inventories and every ancestor directory are already
                # pinned. Never resolve a path through mutable worker parents.
                for relative, expected in config["runtime_records"].items():
                    if (
                        sha(
                            trees[0].read_metadata(
                                relative,
                                uid=expected["uid"],
                                mode=expected["mode"],
                            )
                        )
                        != expected["sha256"]
                    ):
                        raise CleanupRejected("runtime_binding_changed")

        output = perform(trees, verify, progress)
        status = 0
    except (
        CleanupRejected,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        output = {
            "scope": "fixed_live_six_retained_artifact_cleanup_only",
            "run_id": RUN,
            "cleanup_result": "unknown",
            "original_experiment_result": "unknown",
            "failure_stage": progress["stage"],
            "failure_reason": str(error)
            if isinstance(error, CleanupRejected)
            else "cleanup_operation_unknown",
            "original_ledger_write_operations": 0,
            "auth_model_reexecs": 0,
            "network_operations": 0,
            "database_operations": 0,
            "service_mutations": 0,
            "nft_mutations": 0,
            "budget_refund": 0,
        }
        status = 1
    print(json.dumps(output, sort_keys=True))
    return status
