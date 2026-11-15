"""独立 D1:外层时限终止真实受限 worker 及其唯一自证后代。"""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from paper_radar.replay.contract import ReplayError
from paper_radar.replay.service import replay
from tests.replay_support import restored_demo


def running(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().split()[2]
    except FileNotFoundError:
        return False
    return state != "Z"


@pytest.mark.parametrize("phase", ["after-exec", "before-arm"])
def test_total_deadline_blocks_late_writes_from_real_selftest_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    root, originals = restored_demo(tmp_path)
    wrapper = root / "views/synthetic-worker.py"
    wrapper.write_text(
        f"PHASE = {phase!r}\n"
        + """import os
import sys
import time
from paper_radar.replay import worker
original = worker.selftest
bind = worker._bind_parent_lifetime

def delayed_bind(parent):
    if PHASE == "before-arm":
        (root / "views/descendant-started").write_text(str(os.getpid()))
        time.sleep(2)
    bind(parent)

def delayed(root, probes):
    if len(sys.argv) > 3:
        (root / "views/descendant-started").write_text(str(os.getpid()))
        (root / "views/descendant-executed").write_text("EXECUTED")
        time.sleep(10)
        (root / "views/descendant-late-write").write_text("UNFINISHED_PROBE")
    return original(root, probes)

root = worker.Path(sys.argv[1])
worker._bind_parent_lifetime = delayed_bind
worker.selftest = delayed
worker.__file__ = __file__
raise SystemExit(worker.main())
"""
    )
    run = subprocess.run

    def selected(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        command = [*command]
        command[3] = str(wrapper)
        return run(command, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(subprocess, "run", selected)
    descendant: int | None = None
    try:
        with pytest.raises(ReplayError, match=r"^replay_timeout$"):
            replay(root, originals, timeout_seconds=1)
        descendant = int((root / "views/descendant-started").read_text())
        # 只观察本用例刚创建的后代 PID;容许内核结算 SIGKILL,不接受仍可执行的进程。
        deadline = time.monotonic() + (2.5 if phase == "before-arm" else 0.5)
        while running(descendant) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not running(descendant), "selftest descendant survived worker timeout"
        assert not (root / "views/descendant-late-write").exists()
        if phase == "before-arm":
            assert not (root / "views/descendant-executed").exists()
        assert not list((root / "views").glob(".replay-escape-*"))
    finally:
        if descendant is not None and running(descendant):
            os.kill(descendant, signal.SIGKILL)


@pytest.mark.parametrize("failure", ["prctl", "parent-exited"])
def test_parent_lifetime_installation_fails_closed(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from paper_radar.replay import worker

    class Libc:
        def prctl(self, option: int, value: int, *args: int) -> int:
            assert option == 1 and value == signal.SIGKILL
            return -1 if failure == "prctl" else 0

    monkeypatch.setattr(
        "paper_radar.replay.worker.ctypes.CDLL", lambda *args, **kwargs: Libc()
    )
    monkeypatch.setattr("paper_radar.replay.worker.os.getppid", lambda: 42)
    with pytest.raises(ReplayError, match=r"^isolation_verification_failed$"):
        worker._bind_parent_lifetime(99)
