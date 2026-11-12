"""D1:未知退役临时记录仅阻断新一跳恢复,并完整保全所有来源。"""

import os
import stat
from pathlib import Path

import pytest

from tests.preparation_recovery_support import recovery_case


def snapshot(root: Path) -> dict[Path, tuple[object, ...]]:
    """保全整棵合成树的内容和元数据,排除只读操作可能改变的atime。"""
    result: dict[Path, tuple[object, ...]] = {}
    for path in (root, *root.rglob("*")):
        metadata = path.lstat()
        content = (
            os.readlink(path)
            if stat.S_ISLNK(metadata.st_mode)
            else path.read_bytes()
            if stat.S_ISREG(metadata.st_mode)
            else None
        )
        result[path] = (
            content,
            metadata.st_mode,
            metadata.st_uid,
            metadata.st_gid,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
    return result


def unknown_pending(ledger: Path, outside: Path, kind: str) -> Path:
    name = "not-a-digest" if kind == "invalid-digest" else "f" * 64
    pending = ledger / ("placement-retirement-v1-" + name + ".json.new")
    if kind == "symlink":
        outside.mkdir()
        (outside / "untouched").write_bytes(b"outside ledger: never scan\n")
        pending.symlink_to(outside, target_is_directory=True)
    elif kind == "directory":
        pending.mkdir(mode=0o755)
        (pending / "untouched").write_bytes(b"unknown temporary record\n")
    else:
        pending.write_bytes(b"unknown temporary record; no readable journal format\n")
        pending.chmod(0o640)
    return pending


@pytest.mark.parametrize("seam", ["check", "prepare"])
@pytest.mark.parametrize("kind", ["regular", "symlink", "directory", "invalid-digest"])
def test_unknown_retirement_pending_refuses_before_claim_or_callbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seam: str, kind: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    unknown_pending(model.gate.paths.ledger, tmp_path / "outside-ledger", kind)
    before = snapshot(tmp_path)
    events = []
    with pytest.raises(ValueError, match=r"^failed_preparation_pending_file$"):
        if seam == "check":
            model.gate.check(recover=True)
        else:
            model.gate.prepare(
                lambda: events.append("preflight"),
                lambda: events.append("idle"),
                recover=True,
            )
    assert events == []
    assert not os.path.lexists(model.gate.journal)
    assert model.original.io.writes == []
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", ["regular", "symlink", "directory", "invalid-digest"])
def test_original_source_gate_keeps_existing_unknown_pending_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    unknown_pending(model.source.paths.ledger, tmp_path / "outside-ledger", kind)
    before = snapshot(tmp_path)
    assert model.source.check(recover=True) is True
    assert snapshot(tmp_path) == before
    events = []
    assert (
        model.source.prepare(
            lambda: events.append("preflight"),
            lambda: events.append("idle"),
            recover=True,
        )
        is True
    )
    assert events == ["idle", "preflight"]
    assert model.source.check() is False
    assert model.original.io.writes == []
    assert not os.path.lexists(model.gate.journal)
    # 旧入口只推进自己的日志和marker;其余来源/未知记录/目录外目标保持原样。
    after = snapshot(tmp_path)
    assert after.keys() == before.keys()
    allowed = {
        model.source.journal,
        model.original.new.journal,
        model.source.paths.ledger,
    }
    assert {p: value for p, value in after.items() if p not in allowed} == {
        p: value for p, value in before.items() if p not in allowed
    }


@pytest.mark.parametrize("seam", ["check", "prepare"])
@pytest.mark.parametrize("target", ["own", "source"])
def test_exact_known_pending_retains_controlled_reason_and_preservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seam: str, target: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    journal = model.gate.journal if target == "own" else model.source.journal
    pending = journal.with_name(journal.name + ".new")
    pending.write_bytes(b"known pending publication\n")
    pending.chmod(0o640)
    before = snapshot(tmp_path)
    events = []
    with pytest.raises(ValueError, match=r"^failed_preparation_pending_file$"):
        if seam == "check":
            model.gate.check(recover=True)
        else:
            model.gate.prepare(
                lambda: events.append("preflight"),
                lambda: events.append("idle"),
                recover=True,
            )
    assert events == []
    assert not os.path.lexists(model.gate.journal)
    assert model.original.io.writes == []
    assert snapshot(tmp_path) == before
