"""真实进程共享同一文件汇,验证容量内无丢失和有界淘汰。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from paper_radar.runtime_logging import FileSink, RuntimeLog


def records(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for path in (root / "logs").glob("runtime.jsonl*")
        for line in path.read_bytes().splitlines()
    ]


@pytest.mark.parametrize("missing_parent", [False, True])
def test_missing_selected_root_does_not_create_its_parent_chain(
    tmp_path: Path, missing_parent: bool
) -> None:
    root = (tmp_path / "missing-parent" if missing_parent else tmp_path) / "selected"
    code = """
import sys
from pathlib import Path
from paper_radar.runtime_logging import FileSink, RuntimeLog
root = Path(sys.argv[1])
log = RuntimeLog(FileSink(root))
parent_existed = root.parent.exists()
assert not root.exists()
for _ in range(2):
    log.emit("claimed", component="screening", task_id="a" * 64)
assert not root.exists()
assert root.parent.exists() == parent_existed
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root)], capture_output=True, timeout=15
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == b""
    assert result.stderr.decode() == "运行日志写入失败，业务继续。\n"
    assert list(tmp_path.iterdir()) == []


def test_existing_selected_root_only_creates_logs_on_first_event(
    tmp_path: Path,
) -> None:
    root = tmp_path / "selected"
    root.mkdir()
    log = RuntimeLog(FileSink(root))
    assert list(root.iterdir()) == []
    log.emit("claimed", component="screening", task_id="a" * 64)
    assert [path.name for path in root.iterdir()] == ["logs"]
    assert [record["task_id"] for record in records(root)] == ["a" * 64]


def test_two_processes_rotate_without_lost_or_torn_events(tmp_path: Path) -> None:
    code = """
import sys
from pathlib import Path
from paper_radar.runtime_logging import FileSink, RuntimeLog
log = RuntimeLog(FileSink(Path(sys.argv[1]), max_bytes=1024, max_files=80))
print("ready", flush=True)
sys.stdin.readline()
for n in range(80):
    identity = f"{int(sys.argv[2]) * 1000 + n:064x}"
    log.emit("claimed", component="screening", task_id=identity)
"""
    children = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(tmp_path), str(n)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for n in range(2)
    ]
    for child in children:
        assert child.stdout is not None
        assert child.stdout.readline() == b"ready\n"
    for child in children:
        assert child.stdin is not None
        child.stdin.write(b"go\n")
        child.stdin.flush()
    for child in children:
        out, err = child.communicate(timeout=30)
        assert (child.returncode, out, err) == (0, b"", b"")
    events = records(tmp_path)
    assert len(events) == 160
    assert len({event["task_id"] for event in events}) == 160
    files = list((tmp_path / "logs").glob("runtime.jsonl*"))
    assert 1 < len(files) <= 80
    assert all(path.stat().st_size <= 1024 for path in files)


def test_capacity_evicts_only_oldest_owned_files(tmp_path: Path) -> None:
    log = RuntimeLog(FileSink(tmp_path, max_bytes=1024, max_files=3))
    (tmp_path / "logs").mkdir()
    unrelated = tmp_path / "logs/unrelated.jsonl"
    unrelated.write_bytes(b"leave me")
    for n in range(100):
        log.emit("claimed", component="screening", task_id=f"{n:064x}")
    events = records(tmp_path)
    ids = {int(str(event["task_id"]), 16) for event in events}
    assert 0 < len(events) < 100
    assert ids == set(range(min(ids), 100))
    assert len(list((tmp_path / "logs").glob("runtime.jsonl*"))) == 3
    assert unrelated.read_bytes() == b"leave me"


def test_event_whitelist_and_httpx_records_cannot_persist_payloads(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    import logging

    secret = (
        "SENTINEL_API_COOKIE_AUTH_TDM_SESSION_PROFILE_PROMPT_ABSTRACT_BODY_"
        "EXCERPT_MODEL_RPC_STDERR_TOOL"
    )
    log = RuntimeLog(FileSink(tmp_path))
    log.emit(
        "claimed",
        component="screening",
        task_id="a" * 64,
        payload=secret,
        credential="CLAIM_SECRET",
        renewal_handle="RENEWAL_SECRET",
        contact_email="SENTINEL@example.org",
        proxy="http://SENTINEL_PROXY",
        path="/private/SENTINEL_USER/file",
        hostname="SENTINEL_HOST",
        environment="SENTINEL_ENV",
        url="https://example.org/?token=SENTINEL_URL",
    )
    logger = logging.getLogger("httpx")
    previous_level = logger.level
    try:
        logger.setLevel(logging.INFO)
        assert logger.isEnabledFor(logging.INFO)
        logger.info("HTTP Request: https://example.org/?token=SENTINEL_HTTPX")
    finally:
        logger.setLevel(previous_level)
    text = (tmp_path / "logs/runtime.jsonl").read_text()
    assert "SENTINEL" not in text and "SECRET" not in text
    assert records(tmp_path)[0]["event"] == "claimed"
    out, err = capfd.readouterr()
    assert "SENTINEL" not in out + err


def test_symlink_rejection_warns_once_per_process_without_touching_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    root = tmp_path / "selected"
    root.mkdir()
    (root / "logs").symlink_to(target, target_is_directory=True)
    code = """
import sys
from pathlib import Path
from paper_radar.runtime_logging import FileSink, RuntimeLog
for n in range(3):
    RuntimeLog(FileSink(Path(sys.argv[1]))).emit("claimed", component="screening")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root)], capture_output=True, timeout=15
    )
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr.decode() == "运行日志写入失败，业务继续。\n"
    assert list(target.iterdir()) == []


def test_partial_os_write_failure_does_not_tear_the_next_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = RuntimeLog(FileSink(tmp_path))
    log.emit("claimed", component="screening", task_id="a" * 64)
    original_write = os.write
    phase = 0

    def failing_write(fd: int, payload: Any) -> int:
        nonlocal phase
        if fd != 2 and os.readlink(f"/proc/self/fd/{fd}").endswith("runtime.jsonl"):
            if phase == 0:
                phase = 1
                return original_write(fd, bytes(payload)[:7])
            if phase == 1:
                phase = 2
                raise OSError("PRIVATE_DISK_FAILURE")
        return original_write(fd, payload)

    monkeypatch.setattr(os, "write", failing_write)
    log.emit("failed", component="screening", task_id="a" * 64, kind="timeout")
    log.emit("claimed", component="screening", task_id="b" * 64)
    assert [value["task_id"] for value in records(tmp_path)] == ["a" * 64, "b" * 64]
