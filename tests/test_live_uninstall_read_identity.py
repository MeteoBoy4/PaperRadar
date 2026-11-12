"""卸载只读身份回归:冷文件访问时间不构成内容或锁身份漂移。"""

import fcntl
import os
from pathlib import Path

import pytest

from scripts import live_uninstall as tool
from tests.test_live_uninstall import QuietHost, installed_tree


def cold(path: Path) -> None:
    info = path.stat()
    os.utime(path, ns=(1, info.st_mtime_ns))


@pytest.mark.parametrize("content", [b"", b"fixed bytes"])
def test_cold_read_accepts_access_time_change_only(
    tmp_path: Path, content: bytes
) -> None:
    path = tmp_path / "protected"
    path.write_bytes(content)
    path.chmod(0o600)
    cold(path)
    before = path.stat()
    assert tool.file_bytes(path, tmp_path, os.getuid()) == content
    after = path.stat()
    assert (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) == (
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )


def test_cold_preflight_and_uninstall_preserve_history(tmp_path: Path) -> None:
    root, review = installed_tree(tmp_path)
    ledger = root / "var/lib/paperradar/live-evidence"
    original = {
        p.relative_to(ledger): p.read_bytes() for p in ledger.rglob("*") if p.is_file()
    }
    for path in root.rglob("*"):
        if path.is_file():
            cold(path)
    report = tool.uninstall(review, root=root, owner_uid=os.getuid(), host=QuietHost())
    assert report["status"] == "uninstalled", report
    assert report["history_unchanged"] is True
    assert all((ledger / name).read_bytes() == raw for name, raw in original.items())


def model_locks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tool.protected

    def protected(path: Path, root: Path, owner_uid: int) -> None:
        original(path, tmp_path, os.getuid())

    monkeypatch.setattr(tool, "protected", protected)
    monkeypatch.setattr(tool, "LEDGER", tmp_path)
    for name in ("collection.lock", "collector.lock", "closure.lock"):
        path = tmp_path / name
        path.touch(mode=0o600)
        cold(path)


def test_cold_existing_locks_acquire_without_creating_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_locks(tmp_path, monkeypatch)
    before = {p.name: p.stat().st_ino for p in tmp_path.iterdir()}
    with tool.deployment_locks() as checks:
        assert all(check["status"] == "pass" for check in checks.values()), checks
        with (
            (tmp_path / "collector.lock").open("rb") as other,
            pytest.raises(BlockingIOError),
        ):
            fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert {p.name: p.stat().st_ino for p in tmp_path.iterdir()} == before


def test_real_lock_contention_is_distinct_from_identity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_locks(tmp_path, monkeypatch)
    with (tmp_path / "collector.lock").open("rb") as other:
        fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tool.deployment_locks() as checks:
            assert checks["lock:collector.lock"] == {
                "status": "fail",
                "reason": "deployment_lock_busy",
            }
            assert checks["lock:collection.lock"]["status"] == "pass"
            assert checks["lock:closure.lock"]["status"] == "pass"


@pytest.mark.parametrize("change", ["replace", "content", "mode", "mtime_ns"])
def test_read_rejects_real_changes_with_an_open_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    path = tmp_path / "protected"
    path.write_bytes(b"original")
    path.chmod(0o600)
    original = os.fstat
    calls = 0

    def mutate(fd: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == "replace":
                replacement = tmp_path / "replacement"
                replacement.write_bytes(b"original")
                replacement.chmod(0o600)
                replacement.replace(path)
            elif change == "content":
                path.write_bytes(b"tampered")
            elif change == "mode":
                path.chmod(0o644)
            else:
                info = path.stat()
                os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1))
        return original(fd)

    monkeypatch.setattr(os, "fstat", mutate)
    with pytest.raises(ValueError, match=r"^file_changed$"):
        tool.file_bytes(path, tmp_path, os.getuid())


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "writable"])
def test_unsafe_files_remain_rejected(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "protected"
    path.write_bytes(b"original")
    path.chmod(0o600)
    if kind == "symlink":
        path.rename(tmp_path / "target")
        path.symlink_to(tmp_path / "target")
    elif kind == "hardlink":
        os.link(path, tmp_path / "alias")
    else:
        path.chmod(0o620)
    reason = "file_identity" if kind == "hardlink" else "protected_identity"
    with pytest.raises(ValueError, match="^" + reason + "$"):
        tool.file_bytes(path, tmp_path, os.getuid())


def test_lock_replacement_after_read_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_locks(tmp_path, monkeypatch)
    original = tool.file_bytes

    def replace(path: Path, root: Path, owner_uid: int) -> bytes:
        result = original(path, root, owner_uid)
        if path.name == "collector.lock":
            replacement = tmp_path / "replacement"
            replacement.touch(mode=0o600)
            replacement.replace(path)
        return result

    monkeypatch.setattr(tool, "file_bytes", replace)
    with tool.deployment_locks() as checks:
        assert checks["lock:collector.lock"] == {
            "status": "fail",
            "reason": "lock_identity_changed",
        }
        assert checks["lock:collection.lock"]["status"] == "pass"
        assert checks["lock:closure.lock"]["status"] == "pass"


@pytest.mark.parametrize("tampered", [False, True])
def test_cold_tool_identity_checks_still_enforce_expected_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tampered: bool
) -> None:
    from typing import Any

    original_protected = tool.protected
    original_resolve = Path.resolve
    payload = "a" * 64
    bundles = tmp_path / "bundles"
    runtime = bundles / payload / "runtime"
    runtime.mkdir(parents=True)
    binaries = tmp_path / "tools"
    binaries.mkdir()
    mapped: dict[str, Path] = {}
    identities = {}
    for name in (
        "/usr/bin/busctl",
        "/usr/bin/loginctl",
        "/usr/bin/systemctl",
        "/usr/sbin/nft",
        "/usr/sbin/visudo",
    ):
        binary = binaries / Path(name).name
        binary.write_bytes(b"known bytes")
        binary.chmod(0o755)
        identities[name] = {
            "resolved": str(binary),
            "sha256": tool.sha(binary.read_bytes()),
        }
        mapped[name] = binary
    (runtime / "deployment.json").write_bytes(
        tool.canonical({"host_tools": identities})
    )
    if tampered:
        mapped["/usr/sbin/nft"].write_bytes(b"other bytes")
    for path in tmp_path.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
        if path.is_file():
            cold(path)

    def protected(path: Path, root: Path, owner_uid: int) -> None:
        original_protected(path, tmp_path, os.getuid())

    def resolve(path: Path, strict: bool = False) -> Path:
        return (
            mapped[str(path)]
            if str(path) in mapped
            else original_resolve(path, strict=strict)
        )

    def no_host_operations(self: tool.SystemHost, action: str) -> dict[str, Any]:
        assert action == "diagnose"
        return {}

    monkeypatch.setattr(tool, "BUNDLES", bundles)
    monkeypatch.setattr(tool, "protected", protected)
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(tool.SystemHost, "_run", no_host_operations)
    result = tool.SystemHost({"deployment": [payload, "b" * 64]}).diagnose()
    assert result["tools"] == (
        {"status": "fail", "reason": "host_tool_identity"}
        if tampered
        else {"status": "pass", "reason": "host_tools_match"}
    )
