"""Literal stdin bootstrap for one owner-invoked sudo; never reads a password."""

from __future__ import annotations

import hashlib
import json
import os
import re
import resource
import stat
import sys
from pathlib import Path

MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024


class BootstrapRejected(ValueError):
    pass


def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapRejected("duplicate_key")
        result[key] = value
    return result


def read_member(directory_fd: int, name: str, uid: int, limit: int) -> bytes:
    if re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None or name in {".", ".."}:
        raise BootstrapRejected("member_name_invalid")
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
        dir_fd=directory_fd,
    )
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != uid
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > limit
        ):
            raise BootstrapRejected("source_metadata_invalid")
        raw = bytearray()
        while len(raw) <= limit:
            part = os.read(descriptor, min(65536, limit + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        if len(raw) > limit:
            raise BootstrapRejected("source_too_large")
        return bytes(raw)
    finally:
        os.close(descriptor)


def source_bytes(
    source: Path, expected_sha: str, uid: int, gid: int
) -> tuple[dict[str, bytes], Path]:
    if re.fullmatch(r"[a-f0-9]{64}", expected_sha) is None or uid <= 0 or gid <= 0:
        raise BootstrapRejected("binding_invalid")
    descriptor = os.open(
        source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        if os.fstat(descriptor).st_uid != uid:
            raise BootstrapRejected("source_owner_invalid")
        raw_manifest = read_member(descriptor, "manifest.json", uid, 65536)
        if hashlib.sha256(raw_manifest).hexdigest() != expected_sha:
            raise BootstrapRejected("manifest_changed")
        manifest = json.loads(raw_manifest, object_pairs_hook=unique)
        if (
            type(manifest) is not dict
            or set(manifest) != {"kind", "members", "tools"}
            or manifest["kind"] != "h1_synthetic_local_review"
            or type(manifest["members"]) is not dict
            or len(manifest["members"]) > 40
        ):
            raise BootstrapRejected("manifest_invalid")
        validated = {"manifest.json": raw_manifest}
        total = len(raw_manifest)
        for name, digest in manifest["members"].items():
            if (
                type(name) is not str
                or type(digest) is not str
                or re.fullmatch(r"[a-f0-9]{64}", digest) is None
            ):
                raise BootstrapRejected("member_invalid")
            raw = read_member(descriptor, name, uid, MAX_FILE)
            total += len(raw)
            if total > MAX_TOTAL or hashlib.sha256(raw).hexdigest() != digest:
                raise BootstrapRejected("member_changed")
            validated[name] = raw
        plan = json.loads(validated["plan.json"], object_pairs_hook=unique)
        run = plan.get("run_id") if type(plan) is dict else None
        if type(run) is not str or re.fullmatch(r"[a-f0-9]{12}", run) is None:
            raise BootstrapRejected("plan_invalid")
        if (
            type(plan.get("uid")) is not int
            or plan["uid"] != uid
            or type(plan.get("gid")) is not int
            or plan["gid"] != gid
        ):
            raise BootstrapRejected("plan_identity_invalid")
        target = Path(f"/home/paperradar-probes/issue167-{run}")
        if plan.get("install_root") != str(target):
            raise BootstrapRejected("plan_root_invalid")
        required = {
            "synthetic-python",
            "issue167_h1_owner_run.py",
            "issue167_h1_owner_ops.py",
            "issue167_h1_guardian.py",
            "issue167_h1_phase.py",
            "issue167_h1_network_worker.py",
            "host-context.json",
            "retry-context.json",
        }
        if not required <= validated.keys():
            raise BootstrapRejected("members_incomplete")
        # Full Plan validation occurs from the root-owned module before install/start.
        return validated, target
    finally:
        os.close(descriptor)


def protect_directory(path: Path) -> None:
    for item in (path, *path.parents):
        info = item.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise BootstrapRejected("root_parent_invalid")


def install_validated(members: dict[str, bytes], target: Path) -> None:
    if (
        re.fullmatch(r"/home/paperradar-probes/issue167-[a-f0-9]{12}", str(target))
        is None
    ):
        raise BootstrapRejected("target_invalid")
    if any(
        re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None or name in {".", ".."}
        for name in members
    ):
        raise BootstrapRejected("member_name_invalid")
    protect_directory(target.parent.parent)
    if not target.parent.exists():
        target.parent.mkdir(mode=0o700)
        target.parent.chmod(0o755)  # Only a newly created project parent.
    protect_directory(target.parent)
    if stat.S_IMODE(target.parent.stat().st_mode) != 0o755:
        raise BootstrapRejected("root_parent_mode_invalid")
    target.mkdir(mode=0o700, exist_ok=False)
    directory_fd = os.open(
        target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    created: list[tuple[str, int, int]] = []
    try:
        os.fchmod(directory_fd, 0o755)
        for name, raw in members.items():
            fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            info = os.fstat(fd)
            created.append((name, info.st_dev, info.st_ino))
            with os.fdopen(fd, "wb") as output:
                output.write(raw)
                os.fchmod(
                    output.fileno(), 0o755 if name == "synthetic-python" else 0o644
                )
                output.flush()
                os.fsync(output.fileno())
        os.fsync(directory_fd)
    except BaseException:
        # Remove only entries this invocation created, never recurse into unknown data.
        for name, device, inode in reversed(created):
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == (
                device,
                inode,
            ):
                os.unlink(name, dir_fd=directory_fd)
        if not os.listdir(directory_fd):
            target.rmdir()
        raise
    finally:
        os.close(directory_fd)


def main() -> None:
    if os.geteuid() != 0 or len(sys.argv) != 5:
        raise BootstrapRejected("root_binding_required")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source, expected, uid, gid = (
        Path(sys.argv[1]),
        sys.argv[2],
        int(sys.argv[3]),
        int(sys.argv[4]),
    )
    members, target = source_bytes(source, expected, uid, gid)
    plan = json.loads(members["plan.json"], object_pairs_hook=unique)
    run = plan["run_id"]
    for prior in (
        Path(f"/run/paperradar-issue167-{run}"),
        Path(f"/var/lib/paperradar/probe-runs/issue167-{run}.json"),
    ):
        try:
            prior.lstat()
        except FileNotFoundError:
            continue
        raise BootstrapRejected("case_already_present")
    install_validated(members, target)
    if hashlib.sha256((target / "manifest.json").read_bytes()).hexdigest() != expected:
        raise BootstrapRejected("installed_manifest_changed")
    os.execv(
        target / "synthetic-python",
        [
            str(target / "synthetic-python"),
            "-I",
            "-S",
            "-B",
            str(target / "issue167_h1_owner_run.py"),
            "--expected-manifest-sha",
            expected,
        ],
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print(
            json.dumps(
                {
                    "owner_result": "unknown",
                    "failure_stage": "bootstrap",
                    "manual_review_required": True,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(1) from None
