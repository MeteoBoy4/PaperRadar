"""Independent D1 startup race regressions; temporary metadata only, no services."""

import json
import os
import stat
import time
from pathlib import Path

import pytest

from scripts import issue167_h1_network_worker as worker
from scripts.issue167_h1_phase import Plan


class TempPlan(Plan):
    __test__ = False
    directory: Path

    @property
    def runtime_root(self) -> Path:
        return self.directory


def runtime_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    initial: int = 0,
    progress: bool = True,
    payload: bytes | None = None,
) -> tuple[Plan, dict[str, int], list[int]]:
    plan = TempPlan("6e70b5a31d42", os.getuid(), os.getgid())
    object.__setattr__(plan, "directory", tmp_path / "runtime")
    root = plan.runtime_root
    root.mkdir(mode=0o700)
    own = root / "worker"
    own.mkdir(mode=0o700)
    marker = root / "runtime-ready.json"
    marker.write_bytes(
        payload
        or json.dumps({"run_id": plan.run_id, "state": "runtime_ready"}).encode()
    )
    marker.chmod(0o644)
    original_lstat = Path.lstat
    original_fstat = os.fstat
    marker_inode = original_lstat(marker).st_ino
    state = {
        "tick": initial,
        "sleeps": 0,
        "root_mode": 0o700 if initial == 0 else 0o755,
        "worker_owner": 0 if initial < 2 else plan.uid,
        "visible": int(initial >= 2),
        "marker_owner": 0,
    }
    premature: list[int] = []

    def replaced(
        info: os.stat_result, *, mode: int | None = None, owner: int | None = None
    ) -> os.stat_result:
        return os.stat_result(
            (
                info.st_mode if mode is None else mode,
                info.st_ino,
                info.st_dev,
                info.st_nlink,
                info.st_uid if owner is None else owner,
                info.st_gid,
                info.st_size,
                info.st_atime,
                info.st_mtime,
                info.st_ctime,
            )
        )

    def metadata(path: Path) -> os.stat_result:
        info = original_lstat(path)
        if path == root:
            return replaced(info, mode=stat.S_IFDIR | state["root_mode"], owner=0)
        if path == own:
            if not state["visible"]:
                premature.append(state["tick"])
            return replaced(info, owner=state["worker_owner"])
        if path == marker:
            if not state["visible"]:
                raise FileNotFoundError
            return replaced(info, owner=state["marker_owner"])
        return info

    def descriptor_metadata(descriptor: int) -> os.stat_result:
        info = original_fstat(descriptor)
        if info.st_ino == marker_inode:
            return replaced(info, owner=state["marker_owner"])
        return info

    def initialization_step(_seconds: float) -> None:
        state["sleeps"] += 1
        state["tick"] += 1
        assert state["sleeps"] <= 4
        if progress:
            state["root_mode"] = 0o755
            if state["tick"] >= 2:
                state["worker_owner"] = plan.uid
                state["visible"] = 1

    monkeypatch.setattr(Path, "lstat", metadata)
    monkeypatch.setattr(os, "fstat", descriptor_metadata)
    monkeypatch.setattr(time, "monotonic", lambda: state["tick"])
    monkeypatch.setattr(time, "sleep", initialization_step)
    return plan, state, premature


@pytest.mark.parametrize("initial", [0, 1])
def test_worker_waits_for_atomic_completion_not_transient_mode_or_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial: int,
) -> None:
    plan, state, premature = runtime_fixture(tmp_path, monkeypatch, initial=initial)
    assert worker.wait_directories(plan, deadline=4) == plan.runtime_root / "worker"
    assert state["sleeps"] == 2 - initial
    assert premature == []


def test_after_valid_marker_wrong_worker_owner_is_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, state, _ = runtime_fixture(tmp_path, monkeypatch, initial=2)
    state["worker_owner"] = 0
    with pytest.raises(worker.WorkerRejected, match=r"^runtime_metadata_invalid$"):
        worker.wait_directories(plan, deadline=4)
    assert state["sleeps"] == 0


def test_user_owned_completion_marker_is_rejected_before_worker_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, state, premature = runtime_fixture(tmp_path, monkeypatch, initial=2)
    state["marker_owner"] = plan.uid
    with pytest.raises(
        worker.WorkerRejected, match=r"^runtime_ready_metadata_invalid$"
    ):
        worker.wait_directories(plan, deadline=4)
    assert state["sleeps"] == 0 and premature == []


@pytest.mark.parametrize(
    "payload",
    [
        b'{"run_id":"wrong","state":"runtime_ready"}',
        b'{"run_id":"6e70b5a31d42","state":"other","state":"runtime_ready"}',
        b'{"run_id":"6e70b5a31d42","state":"runtime_ready","extra":true}',
        b"not-json",
    ],
)
def test_completion_payload_mismatch_or_ambiguity_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    plan, state, _ = runtime_fixture(tmp_path, monkeypatch, initial=2, payload=payload)
    with pytest.raises(worker.WorkerRejected, match=r"^runtime_ready_invalid$"):
        worker.wait_directories(plan, deadline=4)
    assert state["sleeps"] == 0


def test_absent_completion_marker_times_out_without_worker_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, state, premature = runtime_fixture(
        tmp_path, monkeypatch, initial=1, progress=False
    )
    with pytest.raises(worker.WorkerRejected, match=r"^runtime_timeout$"):
        worker.wait_directories(plan, deadline=4)
    assert state["sleeps"] == 3 and premature == []


def test_atomic_two_link_publication_is_not_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, _state, _ = runtime_fixture(tmp_path, monkeypatch, initial=2)
    marker = plan.runtime_root / "runtime-ready.json"
    os.link(marker, plan.runtime_root / "temporary-marker")

    def forbidden(_fd: int, _size: int) -> bytes:
        pytest.fail("two-link publication must not be consumed")

    monkeypatch.setattr(os, "read", forbidden)
    with pytest.raises(FileNotFoundError):
        worker.read_runtime_ready(marker, plan.run_id)


def test_symlink_completion_marker_is_never_followed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, _state, _ = runtime_fixture(tmp_path, monkeypatch, initial=2)
    marker = plan.runtime_root / "runtime-ready.json"
    marker.unlink()
    target = plan.runtime_root / "untrusted"
    target.write_text('{"run_id":"6e70b5a31d42","state":"runtime_ready"}')
    marker.symlink_to(target)
    with pytest.raises(
        worker.WorkerRejected, match=r"^runtime_ready_metadata_invalid$"
    ):
        worker.wait_directories(plan, deadline=4)


@pytest.mark.parametrize("mode", [0o750, 0o777])
def test_unapproved_root_mode_is_not_treated_as_initialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
) -> None:
    plan, state, _ = runtime_fixture(tmp_path, monkeypatch, initial=2)
    state["root_mode"] = mode
    with pytest.raises(worker.WorkerRejected, match=r"^runtime_metadata_invalid$"):
        worker.wait_directories(plan, deadline=4)
    assert state["sleeps"] == 0
