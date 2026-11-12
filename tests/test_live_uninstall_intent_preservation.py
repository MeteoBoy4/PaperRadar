"""卸载保留原只追加日志的专用信任边界。"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts import live_uninstall as tool
from tests.test_live_uninstall import QuietHost, installed_tree


def model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], Path]:
    root, review = installed_tree(tmp_path)
    runtime = root / tool.RUNTIME.relative_to("/")
    (runtime / "site.json").write_bytes(
        tool.canonical({"product_uid": os.getuid(), "product_gid": os.getgid()})
    )
    manifest = "".join(
        f"{tool.sha(p.read_bytes())}  {p.relative_to(runtime)}\n"
        for p in sorted(runtime.rglob("*"))
        if p.is_file() and p.name not in {"manifest.sha256", "payload.sha256"}
    ).encode()
    (runtime / "manifest.sha256").write_bytes(manifest)
    review["deployment"][1] = tool.sha(manifest)
    journal = root / tool.JOURNAL.relative_to("/")
    data = json.loads(journal.read_bytes())
    data["manifest"] = tool.sha(manifest)
    journal.write_bytes(tool.canonical(data))
    review["journal_sha256"] = tool.sha(journal.read_bytes())
    intent = root / "var/lib/paperradar/live-evidence-intents/pending.jsonl"
    intent.parent.mkdir(mode=0o755)
    intent.write_bytes(b'{"synthetic":"historical tightening; do not rewrite"}\n')
    intent.chmod(0o660)
    monkeypatch.setattr(tool, "intent_flags", lambda fd: 0x20, raising=False)
    return root, review, intent


def test_append_only_history_survives_uninstall_and_is_archived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, review, intent = model(tmp_path, monkeypatch)
    before = (
        intent.read_bytes(),
        intent.stat().st_ino,
        intent.stat().st_mode,
        intent.stat().st_gid,
    )
    report = tool.uninstall(review, root=root, owner_uid=os.getuid(), host=QuietHost())
    assert report["status"] == "uninstalled", report
    assert (
        intent.read_bytes(),
        intent.stat().st_ino,
        intent.stat().st_mode,
        intent.stat().st_gid,
    ) == before
    archived = Path(report["archive"]) / "intents/pending.jsonl"
    assert archived.read_bytes() == before[0]
    assert archived.stat().st_mode & 0o777 == 0o600
    assert report["history_unchanged"] is True


@pytest.mark.parametrize("flags", [0, 0x10, 0x30])
def test_intent_without_exact_append_only_protection_refuses_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: int
) -> None:
    root, review, intent = model(tmp_path, monkeypatch)
    before = intent.read_bytes()
    monkeypatch.setattr(tool, "intent_flags", lambda fd: flags)
    host = QuietHost()
    report = tool.uninstall(review, root=root, owner_uid=os.getuid(), host=host)
    assert report["status"] == "refused"
    assert report["checks"]["preserved"]["reason"] == "intent_identity"
    assert intent.read_bytes() == before
    assert not host.events
    assert not list((root / "var/backups").iterdir())


@pytest.mark.parametrize("change", ["gid", "mode", "hardlink", "other_writable"])
def test_append_only_exception_is_narrow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    root, review, intent = model(tmp_path, monkeypatch)
    if change == "gid":
        monkeypatch.setattr(tool, "product_gid", lambda root, owner: os.getgid() + 1)
    elif change == "mode":
        intent.chmod(0o666)
    elif change == "hardlink":
        os.link(intent, intent.parent / "alias")
    else:
        other = intent.parent / "other.jsonl"
        other.write_bytes(b"untrusted group-writable file")
        other.chmod(0o660)
    report = tool.uninstall(review, root=root, owner_uid=os.getuid(), host=QuietHost())
    assert report["status"] == "refused"
    assert report["checks"]["preserved"]["reason"] in {
        "intent_identity",
        "protected_identity",
    }
    assert not list((root / "var/backups").iterdir())


def test_intent_lock_prevents_concurrent_append_and_never_changes_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fcntl

    root, _, intent = model(tmp_path, monkeypatch)
    before = intent.read_bytes()
    with tool.deployment_locks(root=root, owner_uid=os.getuid()) as checks:
        assert checks["lock:intents"]["status"] == "pass", checks
        with intent.open("rb") as other, pytest.raises(BlockingIOError):
            fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    with intent.open("rb") as other:
        fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tool.deployment_locks(root=root, owner_uid=os.getuid()) as checks:
            assert checks["lock:intents"] == {
                "status": "fail",
                "reason": "deployment_lock_busy",
            }
    assert intent.read_bytes() == before


def test_intent_append_during_read_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, intent = model(tmp_path, monkeypatch)
    original = os.fstat
    count = 0

    def changed(fd: int) -> os.stat_result:
        nonlocal count
        count += 1
        if count == 3:
            with intent.open("ab") as stream:
                stream.write(b'{"synthetic":"concurrent append"}\n')
        return original(fd)

    monkeypatch.setattr(os, "fstat", changed)
    with pytest.raises(ValueError, match=r"^intent_changed$"):
        tool.intent_bytes(root, os.getuid(), os.getgid())


def test_intent_flags_uses_read_only_ioctl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import array

    calls: list[int] = []

    def ioctl(fd: int, command: int, buffer: array.array[int], mutate: bool) -> int:
        calls.append(command)
        buffer[0] = 0x20
        return 0

    monkeypatch.setattr(tool.fcntl, "ioctl", ioctl)
    monkeypatch.setattr(tool.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(tool.sys, "platform", "linux")
    assert tool.intent_flags(123) == 0x20
    assert calls == [0x80086601]
