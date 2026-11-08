"""独立D1:只测元数据解析/拒绝/合成控制流,绝不执行真实崩溃。"""

import json
import os
import struct
from pathlib import Path

import pytest

from scripts import issue167_core_limit as core


def event(mask: int, name: bytes = b"") -> bytes:
    encoded = name + b"\0" if name else b""
    encoded += b"\0" * (-len(encoded) % 4)
    return struct.pack("iIII", 1, mask, 0, len(encoded)) + encoded


def test_unpack_new_members_without_reading_contents() -> None:
    payload = event(0x100, b"created") + event(0x80, b"moved-in")
    payload += event(0x200, b"deleted") + event(0x2, b"modified")
    entries, complete = core.unpack_events(payload)
    assert entries == [(0x100, "created"), (0x80, "moved-in")]
    assert complete is True


@pytest.mark.parametrize("payload", [b"x", event(0x100, b"name")[:-1]])
def test_truncated_event_is_incomplete(payload: bytes) -> None:
    entries, complete = core.unpack_events(payload)
    assert entries == []
    assert complete is False


@pytest.mark.parametrize("mask", [0x4000, 0x8000, 0x2000, 0x800])
def test_coverage_loss_is_incomplete(mask: int) -> None:
    entries, complete = core.unpack_events(event(mask))
    assert entries == []
    assert complete is False


def test_candidate_requires_exact_executable_uid_pid_and_shape() -> None:
    sample = Path("/home/synthetic/example.bin")
    prefix = "core._home_synthetic_example_bin.1000.boot-id.4321.123"
    assert core.candidate_name(prefix, sample, 4321, 1000)
    for candidate in (
        prefix.replace("_example_bin", "_example_bin_extra"),
        prefix.replace(".1000.", ".10000."),
        prefix.replace(".4321.", ".43210."),
        prefix.replace("core.", "not-core."),
        prefix + ".extra",
        prefix.removesuffix(".123"),
    ):
        assert not core.candidate_name(candidate, sample, 4321, 1000)


def test_membership_watch_sees_transient_creation_and_move(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    observer = core.MembershipWatch(watched)
    try:
        created = watched / "synthetic-sentinel"
        created.write_bytes(b"synthetic")
        created.unlink()
        moved = tmp_path / "outside-sentinel"
        moved.write_bytes(b"synthetic")
        moved.rename(watched / "moved-sentinel")
        observer.drain()
        assert (0x100, "synthetic-sentinel") in observer.events
        assert (0x80, "moved-sentinel") in observer.events
        assert observer.complete is True
        assert not created.exists()
    finally:
        observer.close()


def no_crash(*_args: object, **_kwargs: object) -> dict[str, object]:
    pytest.fail("hermetic test must not invoke run_case")


def pretend_home(monkeypatch: pytest.MonkeyPatch, sample: Path) -> None:
    """只替换当前合成路径的/home分类,不在/home创建或执行文件。"""
    original = Path.is_relative_to

    def classified(path: Path, other: str | Path) -> bool:
        return (path == sample and other == "/home") or original(path, other)

    monkeypatch.setattr(Path, "is_relative_to", classified)


def test_run_rejects_outside_home_before_any_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = tmp_path / "synthetic-file"
    sample.write_bytes(b"not-an-executable")
    monkeypatch.setattr(core, "run_case", no_crash)
    receipt = tmp_path / "receipt.json"
    with pytest.raises(ValueError, match=r"^sample_not_owned_home_file$"):
        core.run(sample, receipt)
    assert not receipt.exists()


def test_run_rejects_nonowner_before_any_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = tmp_path / "synthetic-file"
    sample.write_bytes(b"not-an-executable")
    pretend_home(monkeypatch, sample)
    original = Path.stat
    info = list(sample.stat())
    info[4] = os.getuid() + 1
    wrong_owner = os.stat_result(info)

    def metadata(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if path == sample:
            return wrong_owner
        return original(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", metadata)
    monkeypatch.setattr(core, "run_case", no_crash)
    receipt = tmp_path / "receipt.json"
    with pytest.raises(ValueError, match=r"^sample_not_owned_home_file$"):
        core.run(sample, receipt)
    assert not receipt.exists()


def test_existing_receipt_prevents_repeat_before_any_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = tmp_path / "synthetic-file"
    sample.write_bytes(b"not-an-executable")
    pretend_home(monkeypatch, sample)
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(b"reserved-original")
    monkeypatch.setattr(core, "run_case", no_crash)
    with pytest.raises(ValueError, match=r"^receipt_exists_no_repeat$"):
        core.run(sample, receipt)
    assert receipt.read_bytes() == b"reserved-original"


@pytest.mark.parametrize("first_unknown", [True, False])
def test_unknown_case_stops_pair_and_receipt_stays_nonrepeatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first_unknown: bool
) -> None:
    sample = tmp_path / "synthetic-file"
    sample.write_bytes(b"not-an-executable")
    pretend_home(monkeypatch, sample)
    receipt = tmp_path / "receipt.json"
    calls: list[int] = []

    def fake_case(_sample: Path, limit: int) -> dict[str, object]:
        # 真实run_case始终被替换,只观察排他预占是否早于合成派发。
        assert json.loads(receipt.read_text()) == {"state": "reserved_no_auto_retry"}
        calls.append(limit)
        return {
            "limit": limit,
            "result": "unknown" if first_unknown or limit != 0 else "observed_expected",
        }

    monkeypatch.setattr(core, "run_case", fake_case)
    result = core.run(sample, receipt)
    assert calls == ([0] if first_unknown else [0, core.NONZERO_LIMIT])
    assert result["result"] == "unknown"
    assert json.loads(receipt.read_text()) == result
    with pytest.raises(ValueError, match=r"^receipt_exists_no_repeat$"):
        core.run(sample, receipt)
    assert len(calls) == (1 if first_unknown else 2)


def test_watched_directory_deletion_immediately_loses_coverage() -> None:
    entries, complete = core.unpack_events(event(0x400))  # IN_DELETE_SELF
    assert entries == []
    assert complete is False
