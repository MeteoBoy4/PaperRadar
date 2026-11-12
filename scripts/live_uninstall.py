"""Owner-reviewed, one-sudo removal of the Live deployment; no history writes.

Run with system Python -I -S -B. No workspace imports, shell commands, inherited
command environment, new sealed deployment, or policy load are used.
"""

from __future__ import annotations

import argparse
import array
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

RUNTIME = Path("/usr/libexec/paperradar/live-evidence-runtime")
LEDGER = Path("/var/lib/paperradar/live-evidence")
BUNDLES = Path("/var/lib/paperradar/live-bundles")
EXECUTABLES = RUNTIME.parent
JOURNAL = LEDGER / "deployment-v2.json"
INTENT_PATH = Path("/var/lib/paperradar/live-evidence-intents/pending.jsonl")
MAX_INTENT_BYTES = 8 * 1024 * 1024
RESOURCE_SOURCES = {
    **{
        str(EXECUTABLES / ("live-evidence-" + name)): "wrappers/" + name
        for name in ("collect", "tighten", "owner", "refresh", "model-collect")
    },
    "/etc/sudoers.d/paperradar-live-evidence": "sudoers",
    "/etc/systemd/user/paperradar.slice": "resources/paperradar.slice",
    "/etc/systemd/user/paperradar-anchor.service": (
        "resources/paperradar-anchor.service"
    ),
    "/run/paper-radar/resolv.conf": "resources/resolv.conf",
}
ENVIRONMENT = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def location(root: Path, path: Path | str) -> Path:
    return root / str(path).lstrip("/")


def protected(path: Path, root: Path, owner_uid: int) -> None:
    for item in (path, *path.parents):
        info = item.lstat()
        if (
            info.st_uid != owner_uid
            or info.st_mode & 0o022
            or stat.S_ISLNK(info.st_mode)
        ):
            raise ValueError("protected_identity")
        if item == root:
            return
    raise ValueError("protected_path")


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    """Security/content identity excludes atime, which this read can update."""
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def file_bytes(path: Path, root: Path, owner_uid: int) -> bytes:
    protected(path, root, owner_uid)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError("file_identity")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as source:
        if file_identity(os.fstat(source.fileno())) != file_identity(before):
            raise ValueError("file_changed")
        raw = source.read()
        after = os.fstat(source.fileno())
        protected(path, root, owner_uid)
        if file_identity(after) != file_identity(before) or file_identity(
            path.lstat()
        ) != file_identity(before):
            raise ValueError("file_changed")
    return raw


def product_gid(root: Path, owner_uid: int) -> int:
    site = json.loads(
        file_bytes(location(root, RUNTIME) / "site.json", root, owner_uid)
    )
    gid = site.get("product_gid")
    if type(gid) is not int or not 0 <= gid < 2**32:
        raise ValueError("product_identity_invalid")
    return gid


def intent_flags(fd: int) -> int:
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise ValueError("intent_identity")
    flags = array.array("I", [0])
    fcntl.ioctl(fd, 0x80086601, flags, True)
    return flags[0]


def intent_fd(root: Path, owner_uid: int, gid: int) -> int:
    """Read-only descriptor for the one existing append-only intent log."""
    path = location(root, INTENT_PATH)
    protected(path.parent, root, owner_uid)
    if stat.S_IMODE(path.parent.lstat().st_mode) != 0o755:
        raise ValueError("intent_identity")
    before = path.lstat()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (
            file_identity(info) != file_identity(before)
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != owner_uid
            or info.st_gid != gid
            or stat.S_IMODE(info.st_mode) != 0o660
            or info.st_nlink != 1
            or info.st_size >= MAX_INTENT_BYTES
            or intent_flags(fd) & 0x30 != 0x20
        ):
            raise ValueError("intent_identity")
        return fd
    except BaseException:
        os.close(fd)
        raise


def intent_bytes(root: Path, owner_uid: int, gid: int) -> bytes:
    path = location(root, INTENT_PATH)
    with os.fdopen(intent_fd(root, owner_uid, gid), "rb") as source:
        before = file_identity(os.fstat(source.fileno()))
        raw = source.read(MAX_INTENT_BYTES + 1)
        if (
            len(raw) >= MAX_INTENT_BYTES
            or file_identity(os.fstat(source.fileno())) != before
            or file_identity(path.lstat()) != before
            or intent_flags(source.fileno()) & 0x30 != 0x20
        ):
            raise ValueError("intent_changed")
    return raw


def snapshot(
    path: Path, root: Path, owner_uid: int, *, intent_gid: int | None = None
) -> dict[str, Any]:
    """Hash the complete protected inventory, treating history solely as bytes."""
    digest = hashlib.sha256()
    count = 0
    for item in (path, *sorted(path.rglob("*"))):
        is_intent = intent_gid is not None and item == location(root, INTENT_PATH)
        if not is_intent:
            protected(item, root, owner_uid)
        info = item.lstat()
        relative = "." if item == path else item.relative_to(path).as_posix()
        if stat.S_ISDIR(info.st_mode):
            content = "directory"
        elif is_intent and intent_gid is not None:
            content = sha(intent_bytes(root, owner_uid, intent_gid))
        else:
            content = sha(file_bytes(item, root, owner_uid))
        digest.update(
            canonical(
                [
                    relative,
                    info.st_uid,
                    info.st_gid,
                    stat.S_IMODE(info.st_mode),
                    content,
                ]
            )
        )
        count += 1
    return {"sha256": digest.hexdigest(), "members": count}


def verify_runtime(root: Path, runtime: Path, pair: list[str], owner_uid: int) -> None:
    base = location(root, runtime)
    payload, expected_manifest = pair
    manifest = file_bytes(base / "manifest.sha256", root, owner_uid)
    if sha(manifest) != expected_manifest:
        raise ValueError("runtime_manifest_identity")
    expected = {
        "manifest.sha256": expected_manifest,
        "payload.sha256": sha((payload + "\n").encode()),
    }
    for line in manifest.decode("ascii").splitlines():
        digest, name = line.split("  ", 1)
        if (
            not re.fullmatch("[0-9a-f]{64}", digest)
            or name in expected
            or Path(name).is_absolute()
            or ".." in Path(name).parts
            or str(Path(name)) != name
        ):
            raise ValueError("runtime_manifest_invalid")
        expected[name] = digest
    actual = set()
    directories = {
        str(parent)
        for name in expected
        for parent in Path(name).parents
        if str(parent) != "."
    }
    found_directories = set()
    protected(base, root, owner_uid)
    for path in base.rglob("*"):
        protected(path, root, owner_uid)
        name = path.relative_to(base).as_posix()
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o755:
            found_directories.add(name)
        elif (
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) in {0o644, 0o755}
        ):
            actual.add(name)
            if (
                name not in expected
                or sha(file_bytes(path, root, owner_uid)) != expected[name]
            ):
                raise ValueError("runtime_member_identity")
        else:
            raise ValueError("runtime_member_identity")
    if set(expected) != actual or directories != found_directories:
        raise ValueError("runtime_inventory")


def prepare_review(root: Path, output: Path, *, owner_uid: int = 0) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    try:
        path = location(root, JOURNAL)
        if not path.exists():
            raise ValueError("deployment_missing")
        raw = file_bytes(path, root, owner_uid)
        deployment = json.loads(raw)
        if (
            deployment.get("phase") != "installed"
            or deployment.get("format_version") != 2
        ):
            raise ValueError("deployment_not_installed")
        pair = [deployment["payload"], deployment["manifest"]]
        verify_runtime(root, RUNTIME, pair, owner_uid)
        archives = []
        for directory in sorted(location(root, BUNDLES).iterdir()):
            if not re.fullmatch("[0-9a-f]{64}", directory.name):
                raise ValueError("bundle_unknown")
            runtime = directory / "runtime"
            archive_pair = [
                directory.name,
                sha(file_bytes(runtime / "manifest.sha256", root, owner_uid)),
            ]
            verify_runtime(
                root, BUNDLES / directory.name / "runtime", archive_pair, owner_uid
            )
            archives.append(archive_pair)
        review = {
            "format_version": 1,
            "authorization": "owner-live-deployment-uninstall-v1",
            "deployment": pair,
            "journal_sha256": sha(raw),
            "archives": archives,
            "diagnostic_runtime": next(
                archive
                for archive in reversed(archives)
                if (
                    location(root, BUNDLES)
                    / archive[0]
                    / "runtime/site-packages/paper_radar/live_evidence"
                    / "live_apparmor_kernel.py"
                ).exists()
            ),
        }
        output.write_bytes(canonical(review))
        output.chmod(0o600)
        checks["deployment"] = {"status": "pass", "reason": "review_ready"}
        return {
            "status": "review_ready",
            "checks": checks,
            "sha256": sha(canonical(review)),
        }
    except (OSError, ValueError, KeyError, StopIteration) as error:
        checks["deployment"] = {"status": "fail", "reason": str(error)}
        return {"status": "refused", "checks": checks}


class Host(Protocol):
    def diagnose(self) -> dict[str, Any]: ...
    def action(self, name: str) -> None: ...


def validate_review(review: Any) -> dict[str, Any]:
    if (
        not isinstance(review, dict)
        or set(review)
        != {
            "format_version",
            "authorization",
            "deployment",
            "journal_sha256",
            "archives",
            "diagnostic_runtime",
        }
        or type(review["format_version"]) is not int
        or review["format_version"] != 1
        or review["authorization"] != "owner-live-deployment-uninstall-v1"
        or not isinstance(review["archives"], list)
    ):
        raise ValueError("review_schema")
    pairs = [review["deployment"], review["diagnostic_runtime"], *review["archives"]]
    if any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(
            not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None
            for value in pair
        )
        for pair in pairs
    ):
        raise ValueError("review_identity")
    if (
        not isinstance(review["journal_sha256"], str)
        or re.fullmatch("[0-9a-f]{64}", review["journal_sha256"]) is None
        or review["diagnostic_runtime"] not in review["archives"]
        or review["deployment"] not in review["archives"]
        or len({pair[0] for pair in review["archives"]}) != len(review["archives"])
    ):
        raise ValueError("review_identity")
    return review


class SystemHost:
    """Only the verified pre-existing archive interpreter executes the fixed program."""

    def __init__(self, review: dict[str, Any]) -> None:
        self.review = review

    def _run(self, action: str) -> dict[str, Any]:
        if action not in {
            "diagnose",
            "stop",
            "policy-remove",
            "nft-remove",
            "reload",
            "absent",
        }:
            raise ValueError("host_action_unknown")
        pair = self.review["diagnostic_runtime"]
        runtime = BUNDLES / pair[0] / "runtime"
        verify_runtime(Path("/"), runtime, pair, 0)
        result = subprocess.run(
            (str(runtime / "python/bin/python3"), "-I", "-S", "-B", "-c", HOST_PROGRAM),
            input=canonical({"review": self.review, "action": action}),
            capture_output=True,
            env=ENVIRONMENT,
            cwd="/",
            timeout=180,
            check=False,
        )
        if result.returncode or len(result.stdout) > 65536:
            raise ValueError("host_helper_refused")
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError("host_helper_invalid")
        return value

    def diagnose(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        try:
            path = BUNDLES / self.review["deployment"][0] / "runtime/deployment.json"
            tools = json.loads(file_bytes(path, Path("/"), 0))["host_tools"]
            expected = {
                "/usr/bin/busctl",
                "/usr/bin/loginctl",
                "/usr/bin/systemctl",
                "/usr/sbin/nft",
                "/usr/sbin/visudo",
            }
            if set(tools) != expected:
                raise ValueError("host_tool_identity")
            for name, identity in tools.items():
                resolved = Path(name).resolve(strict=True)
                if (
                    str(resolved) != identity["resolved"]
                    or sha(file_bytes(resolved, Path("/"), 0)) != identity["sha256"]
                ):
                    raise ValueError("host_tool_identity")
            checks["tools"] = {"status": "pass", "reason": "host_tools_match"}
        except ValueError as error:
            reason = str(error)
            if reason not in {
                "file_changed",
                "file_identity",
                "protected_identity",
                "protected_path",
            }:
                reason = "host_tool_identity"
            checks["tools"] = {"status": "fail", "reason": reason}
        except (OSError, KeyError):
            checks["tools"] = {"status": "fail", "reason": "host_tool_unavailable"}
        try:
            checks.update(self._run("diagnose"))
        except (OSError, ValueError, subprocess.SubprocessError):
            checks["host"] = {
                "status": "fail",
                "reason": "host_diagnostics_unavailable",
            }
        return checks

    def action(self, name: str) -> None:
        result = self._run(name)
        if result.get("status") != "pass":
            raise ValueError(result.get("reason", "host_action_refused"))


@contextmanager
def deployment_locks(
    *, root: Path = Path("/"), owner_uid: int = 0
) -> Iterator[dict[str, Any]]:
    descriptors: list[int] = []
    checks: dict[str, Any] = {}
    try:
        for name in ("collection.lock", "collector.lock", "closure.lock"):
            try:
                path = location(root, LEDGER) / name
                before = file_identity(path.lstat())
                file_bytes(path, root, owner_uid)
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                descriptors.append(descriptor)
                if (
                    file_identity(os.fstat(descriptor)) != before
                    or file_identity(path.stat(follow_symlinks=False)) != before
                ):
                    raise ValueError("lock_identity_changed")
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                checks["lock:" + name] = {
                    "status": "pass",
                    "reason": "exclusive_existing_lock",
                }
            except BlockingIOError:
                checks["lock:" + name] = {
                    "status": "fail",
                    "reason": "deployment_lock_busy",
                }
            except ValueError as error:
                checks["lock:" + name] = {"status": "fail", "reason": str(error)}
            except OSError:
                checks["lock:" + name] = {
                    "status": "fail",
                    "reason": "deployment_lock_unavailable",
                }
        if os.path.lexists(
            location(root, LEDGER).parent / "live-evidence-intents/pending.jsonl"
        ):
            try:
                descriptor = intent_fd(root, owner_uid, product_gid(root, owner_uid))
                descriptors.append(descriptor)
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                checks["lock:intents"] = {
                    "status": "pass",
                    "reason": "exclusive_existing_lock",
                }
            except BlockingIOError:
                checks["lock:intents"] = {
                    "status": "fail",
                    "reason": "deployment_lock_busy",
                }
            except ValueError:
                checks["lock:intents"] = {"status": "fail", "reason": "intent_identity"}
            except OSError:
                checks["lock:intents"] = {
                    "status": "fail",
                    "reason": "intent_unavailable",
                }
        yield checks
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def diagnose(
    review: dict[str, Any],
    root: Path,
    owner_uid: int,
    host: Host,
    *,
    created_archive: Path | None = None,
) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    def check(name: str, operation: Any) -> None:
        try:
            operation()
            checks[name] = {"status": "pass", "reason": "identity_matches"}
        except (OSError, ValueError, KeyError) as error:
            checks[name] = {"status": "fail", "reason": str(error)}

    def deployment() -> None:
        raw = file_bytes(location(root, JOURNAL), root, owner_uid)
        if sha(raw) != review["journal_sha256"]:
            raise ValueError("deployment_changed")
        verify_runtime(root, RUNTIME, review["deployment"], owner_uid)

    check("deployment", deployment)

    def archives() -> None:
        actual = sorted(item.name for item in location(root, BUNDLES).iterdir())
        if actual != sorted(pair[0] for pair in review["archives"]):
            raise ValueError("bundle_inventory_changed")
        for pair in review["archives"]:
            verify_runtime(root, BUNDLES / pair[0] / "runtime", pair, owner_uid)

    check("archives", archives)
    for destination, source in RESOURCE_SOURCES.items():

        def resource(destination: str = destination, source: str = source) -> None:
            path = location(root, destination)
            raw = file_bytes(path, root, owner_uid)
            expected_mode = (
                0o440
                if source == "sudoers"
                else 0o755
                if source.startswith("wrappers/")
                else 0o644
            )
            if (
                raw != file_bytes(location(root, RUNTIME) / source, root, owner_uid)
                or stat.S_IMODE(path.lstat().st_mode) != expected_mode
            ):
                raise ValueError("resource_identity")

        check("resource:" + destination, resource)
    check("preserved", lambda: preserved_inventory(root, owner_uid))

    def archive_target() -> None:
        parent = location(root, "/var/backups")
        protected(parent, root, owner_uid)
        archive = parent / ("paperradar-live-uninstall-" + sha(canonical(review)))
        if os.path.lexists(archive) and archive != created_archive:
            raise ValueError("archive_already_exists")
        required = sum(
            path.stat().st_size
            for base in (location(root, RUNTIME), location(root, LEDGER))
            for path in base.rglob("*")
            if path.is_file()
        )
        if shutil.disk_usage(parent).free < required * 2 + 512 * 1024 * 1024:
            raise ValueError("archive_space_insufficient")

    check("archive", archive_target)
    checks.update(host.diagnose())
    return checks


def uninstall(
    review: dict[str, Any],
    *,
    root: Path,
    owner_uid: int,
    host: Host,
    lock_checks: dict[str, Any] | None = None,
    report_diagnostics: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    checks = diagnose(review, root, owner_uid, host)
    checks.update(lock_checks or {})
    if report_diagnostics is not None:
        report_diagnostics(checks)
    if any(item["status"] != "pass" for item in checks.values()):
        return {"status": "refused", "checks": checks}
    archive = location(root, "/var/backups") / (
        "paperradar-live-uninstall-" + sha(canonical(review))
    )
    if archive.exists():
        checks["archive"] = {"status": "fail", "reason": "archive_already_exists"}
        return {"status": "refused", "checks": checks}
    phase = "backup"
    try:
        gid = product_gid(root, owner_uid)
        preserved = preserved_inventory(root, owner_uid, intent_gid=gid)
        protected(archive.parent, root, owner_uid)
        archive.mkdir(mode=0o700)
        shutil.copytree(
            location(root, RUNTIME), archive / "runtime", copy_function=shutil.copy2
        )
        shutil.copytree(
            location(root, LEDGER), archive / "history", copy_function=shutil.copy2
        )
        intents = location(root, "/var/lib/paperradar/live-evidence-intents")
        if intents.exists():
            shutil.copytree(intents, archive / "intents", copy_function=shutil.copy2)
            pending = location(root, INTENT_PATH)
            if pending.exists():
                copied = archive / "intents/pending.jsonl"
                copied.chmod(0o600)
                if file_bytes(copied, archive, owner_uid) != intent_bytes(
                    root, owner_uid, gid
                ):
                    raise ValueError("backup_intents_changed")
                info = pending.lstat()
                (archive / "intents-metadata.json").write_bytes(
                    canonical(
                        {
                            "uid": info.st_uid,
                            "gid": info.st_gid,
                            "mode": stat.S_IMODE(info.st_mode),
                            "append_only": True,
                            "sha256": sha(file_bytes(copied, archive, owner_uid)),
                        }
                    )
                )
        for destination in RESOURCE_SOURCES:
            backup = archive / "resources" / destination.lstrip("/")
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(location(root, destination), backup)
        (archive / "review.json").write_bytes(canonical(review))
        (archive / "preserved-before.json").write_bytes(canonical(preserved))
        verify_runtime(archive, Path("/runtime"), review["deployment"], owner_uid)
        if snapshot(location(root, LEDGER), root, owner_uid) != snapshot(
            archive / "history", archive, owner_uid
        ):
            raise ValueError("backup_history_changed")
        durable(archive)
        if preserved_inventory(root, owner_uid, intent_gid=gid) != preserved:
            raise ValueError("preserved_changed_before_removal")
        repeated = diagnose(review, root, owner_uid, host, created_archive=archive)
        if any(item["status"] != "pass" for item in repeated.values()):
            raise ValueError("preflight_changed")
        phase = "host_removal"
        for action in ("stop", "policy-remove", "nft-remove"):
            host.action(action)
        phase = "file_removal"
        for destination in RESOURCE_SOURCES:
            source = location(root, destination)
            if (
                file_bytes(source, root, owner_uid)
                != (archive / "resources" / destination.lstrip("/")).read_bytes()
            ):
                raise ValueError("resource_changed_before_removal")
            source.unlink()
            sync_directory(source.parent)
        resolver_directory = location(root, "/run/paper-radar")
        if not list(resolver_directory.iterdir()):
            resolver_directory.rmdir()
            sync_directory(resolver_directory.parent)
        host.action("reload")
        verify_runtime(root, RUNTIME, review["deployment"], owner_uid)
        runtime = location(root, RUNTIME)
        members = sorted(
            runtime.rglob("*"), key=lambda path: len(path.parts), reverse=True
        )
        for item in members:
            if item.is_dir():
                item.rmdir()
            else:
                item.unlink()
        runtime.rmdir()
        sync_directory(runtime.parent)
        host.action("absent")
        phase = "preserved_verification"
        if preserved_inventory(root, owner_uid, intent_gid=gid) != preserved:
            raise ValueError("preserved_changed_after_removal")
        report = {
            "status": "uninstalled",
            "checks": checks,
            "archive": str(archive),
            "preserved": preserved,
            "history_unchanged": True,
            "resolver_directory_preserved": resolver_directory.exists(),
        }
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report = {
            "status": "failed",
            "checks": checks,
            "archive": str(archive),
            "phase": phase,
            "reason": str(error),
            "automatic_rollback": False,
        }
    if archive.exists():
        try:
            (archive / "outcome.json").write_bytes(canonical(report))
            durable(archive)
        except OSError:
            report = {
                "status": "failed",
                "checks": checks,
                "archive": str(archive),
                "phase": "outcome",
                "reason": "outcome_not_durable",
                "automatic_rollback": False,
            }
    return report


def preserved_inventory(
    root: Path, owner_uid: int, *, intent_gid: int | None = None
) -> dict[str, Any]:
    if intent_gid is None and os.path.lexists(location(root, INTENT_PATH)):
        intent_gid = product_gid(root, owner_uid)
    result = {
        "/var/lib/paperradar": snapshot(
            location(root, "/var/lib/paperradar"),
            root,
            owner_uid,
            intent_gid=intent_gid,
        )
    }
    for path in sorted(location(root, EXECUTABLES).iterdir()):
        if path.name.startswith("live-evidence-runtime.archive-"):
            result[str(EXECUTABLES / path.name)] = snapshot(path, root, owner_uid)
    return result


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable(path: Path) -> None:
    for item in path.rglob("*"):
        if item.is_file():
            with item.open("rb") as stream:
                os.fsync(stream.fileno())
    for directory in sorted(
        (p for p in path.rglob("*") if p.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        sync_directory(directory)
    sync_directory(path)
    sync_directory(path.parent)


HOST_PROGRAM = r"""
import hashlib
import json
import os
import platform
import re
import sys
from pathlib import Path

request = json.load(sys.stdin)
review = request["review"]
action = request["action"]
archive = Path("/var/lib/paperradar/live-bundles")
diagnostic = archive / review["diagnostic_runtime"][0] / "runtime"
sys.path.insert(0, str(diagnostic / "site-packages"))
from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO
from paper_radar.live_evidence.live_host import LinuxLiveHost, validate_unit_identity
from paper_radar.live_evidence.live_install import InstallationPaths
from paper_radar.live_evidence.model_manifest import parse_manifest
from paper_radar.live_evidence.nft_rules import read_nft_snapshot, verify_nft
from paper_radar.live_evidence.placement_policy import read_placement_policy
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

paths = InstallationPaths()
original = archive / review["deployment"][0] / "runtime"
site = SiteConfiguration.model_validate_json((original / "site.json").read_bytes())
manifest = parse_manifest((original / "model-manifest.json").read_bytes())
host = LinuxLiveHost(paths)
host.site = site


def units():
    anchor = host.unit_properties("paperradar-anchor.service")
    validate_unit_identity(
        paths, host.unit_properties("paperradar.slice"), anchor, require_active=False
    )
    if anchor["ActiveState"] == "active":
        target = host._anchor_target()
        retained = host._read_target()
        if (
            target.anchor_pid,
            target.anchor_start,
            target.anchor_cgroup,
            target.ancestors,
        ) != (
            retained.anchor_pid,
            retained.anchor_start,
            retained.anchor_cgroup,
            retained.ancestors,
        ):
            raise ValueError("anchor_target_changed")
    return anchor


def processes(*, stopped=False):
    retained = host._read_target()
    anchor = units() if not stopped else None
    allowed = (
        int(anchor["MainPID"]) if anchor and anchor["ActiveState"] == "active" else 0
    )
    directory = Path("/sys/fs/cgroup") / retained.ancestors[0].path.lstrip("/")
    if directory.exists():
        info = directory.stat()
        if (
            info.st_dev != retained.ancestors[0].device
            or info.st_ino != retained.ancestors[0].inode
        ):
            raise ValueError("cgroup_identity_changed")
        for source in directory.rglob("cgroup.procs"):
            if set(source.read_text().split()) - ({str(allowed)} if allowed else set()):
                raise ValueError("project_process_active")
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal() or int(directory.name) == allowed:
            continue
        try:
            exe = (directory / "exe").resolve(strict=True)
            if exe.is_relative_to(paths.runtime) or exe.is_relative_to(
                site.install_path
            ):
                raise ValueError("runtime_or_product_process_active")
        except FileNotFoundError:
            continue


def nft():
    inventory = json.loads(host._run(("/usr/sbin/nft", "-j", "list", "tables")))
    for row in inventory["nftables"]:
        table = row.get("table", {})
        if table.get("name") == "paperradar" and table.get("family") != "inet":
            raise ValueError("nft_namespace_conflict")
    value = read_nft_snapshot()
    if value["nftables"]:
        verify_nft(value, host._read_target(), manifest.network)
    return bool(value["nftables"])


def policy():
    io = LinuxKernelPolicyIO()
    found = []
    for handle in io.profile_handles():
        name = io.read_field(handle, "name").rstrip(b"\n").decode("ascii")
        attach = io.read_field(handle, "attach").rstrip(b"\n").decode("ascii")
        if name.startswith("paperradar") or attach.startswith(str(paths.runtime)):
            found.append(
                (name, io.read_field(handle, "raw_sha256").strip().decode("ascii"))
            )
    if not found:
        return None
    if set(name for name, _ in found) - {
        "paperradar-placement-pre-v1",
        "paperradar-placement-post-v1",
    }:
        raise ValueError("apparmor_unknown_owned_name")
    digests = {digest for _, digest in found}
    if len(digests) != 1:
        raise ValueError("apparmor_mixed_policy")
    for pair in review["archives"]:
        root = archive / pair[0] / "runtime"
        candidate = read_placement_policy(root)
        if candidate and candidate.policy.binary_sha256 in digests:
            candidate.kernel().check(candidate.policy, allow_partial=True)
            LinuxKernelPolicyIO().require_writer(candidate.parser)
            return candidate
    raise ValueError("apparmor_unknown_owned_bytes")


def reason(error):
    text = str(error)
    return text if re.fullmatch("[a-z][a-z0-9_]{1,100}", text) else "host_check_failed"


try:
    if action == "diagnose":
        result = {}
        for name, check in (
            ("units", units),
            ("processes", processes),
            ("nft", nft),
            ("apparmor", policy),
        ):
            try:
                value = check()
                result[name] = {"status": "pass", "reason": "known_or_absent"}
                if name == "apparmor":
                    result[name]["removal_required"] = value is not None
            except Exception as error:
                result[name] = {"status": "fail", "reason": reason(error)}
    elif action == "stop":
        units()
        processes()
        host._run(
            (
                "/usr/bin/systemctl",
                "--user",
                "stop",
                "paperradar-anchor.service",
                "paperradar.slice",
            ),
            product=True,
        )
        processes(stopped=True)
        result = {"status": "pass"}
    elif action == "policy-remove":
        candidate = policy()
        if candidate:
            candidate.kernel().remove(candidate.policy, allow_partial=True)
        if policy() is not None:
            raise ValueError("apparmor_remove_incomplete")
        result = {"status": "pass"}
    elif action == "nft-remove":
        if nft():
            host._run(("/usr/sbin/nft", "delete", "table", "inet", "paperradar"))
        if read_nft_snapshot()["nftables"]:
            raise ValueError("nft_remove_incomplete")
        result = {"status": "pass"}
    elif action == "reload":
        host._run(("/usr/bin/systemctl", "--user", "daemon-reload"), product=True)
        result = {"status": "pass"}
    elif action == "absent":
        processes(stopped=True)
        if read_nft_snapshot()["nftables"] or policy() is not None:
            raise ValueError("host_resources_remaining")
        for name in ("paperradar-anchor.service", "paperradar.slice"):
            raw = host._run(
                (
                    "/usr/bin/systemctl",
                    "--user",
                    "show",
                    name,
                    "--property=LoadState,ActiveState,MainPID",
                ),
                product=True,
            )
            values = dict(row.split("=", 1) for row in raw.decode().splitlines())
            if (
                values.get("LoadState") != "not-found"
                or values.get("ActiveState") != "inactive"
                or values.get("MainPID", "0") != "0"
            ):
                raise ValueError("unit_remove_incomplete")
        result = {"status": "pass"}
    else:
        raise ValueError("host_action_unknown")
except Exception as error:
    result = {"status": "fail", "reason": reason(error)}
print(json.dumps(result, sort_keys=True))
"""


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="所有者审阅后一次 sudo 卸载 Live 部署；保留全部历史。"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser(
        "prepare", help="只读核对已安装树并生成私有审阅文件；不调用 sudo。"
    )
    prepare.add_argument("--output", type=Path, required=True)
    apply = commands.add_parser(
        "apply", help="owner 本人审阅后一次 sudo 执行；先聚合诊断，再归档和卸载。"
    )
    apply.add_argument("--review", type=Path, required=True)
    apply.add_argument("--sha256", required=True)
    args = parser.parse_args(arguments)
    if args.command == "prepare":
        if os.geteuid() == 0:
            parser.error("prepare 请以普通所有者身份执行。")
        report = prepare_review(Path("/"), args.output)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["status"] == "review_ready" else 1
    if args.command == "apply":
        if os.geteuid() != 0:
            parser.error("apply 只能由 owner 本人一次 sudo 执行；agent 不执行。")
        try:
            os.umask(0o077)
            raw = args.review.read_bytes()
            if not re.fullmatch("[0-9a-f]{64}", args.sha256) or sha(raw) != args.sha256:
                raise ValueError("review_digest_mismatch")
            review = validate_review(json.loads(raw))
            with deployment_locks() as locks:
                report = uninstall(
                    review,
                    root=Path("/"),
                    owner_uid=0,
                    host=SystemHost(review),
                    lock_checks=locks,
                    report_diagnostics=lambda checks: print(
                        "DIAGNOSTIC_JSON "
                        + json.dumps(checks, ensure_ascii=False, sort_keys=True),
                        flush=True,
                    ),
                )
        except (OSError, ValueError, KeyError) as error:
            report = {"status": "refused", "reason": str(error)}
        print(
            {
                "uninstalled": (
                    "卸载完成：部署入口与主机项目资源已移除，历史原字节保持。"
                ),
                "refused": "卸载已拒绝：未修改部署，请核对全部诊断项。",
                "failed": "卸载中止：保留归档和现场，不自动恢复或加载策略。",
            }[report["status"]]
        )
        print("RESULT_JSON " + json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["status"] == "uninstalled" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
