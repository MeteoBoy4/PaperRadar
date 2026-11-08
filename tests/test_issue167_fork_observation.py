"""Independent D1: event replay + real temporary scans/cgroup fixtures."""

import os
import shutil
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest

from scripts.issue167_fork_observation import (
    CgroupReader,
    ForkObservation,
    TrackedFileObserver,
    WindowRejected,
)
from scripts.issue167_h1_phase import Plan
from scripts.issue167_observation import FileObserver


class ReplayObserver(TrackedFileObserver):
    """Exercise the existing decoder/scanner without kernel watch allocation."""

    def __init__(self, root: Path) -> None:
        read_fd, self._writer = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        backend = SimpleNamespace(inotify_init1=lambda _flags: read_fd)
        with patch("scripts.issue167_observation.ctypes.CDLL", return_value=backend):
            super().__init__(root)

    def _watch(self, _path: Path) -> None:
        pass

    def close(self) -> None:
        if not self.closed:
            os.close(self._writer)
        super().close()


def fixture(tmp_path: Path) -> tuple[Path, CgroupReader, Path]:
    plan = Plan("a123456789ab", 1000, 1000, network_mode="ipv4_only")
    root = tmp_path / "group-root"
    group = root / "system.slice" / plan.unit
    group.mkdir(parents=True)
    (group / "cgroup.procs").write_text("1234\n")
    own = tmp_path / "own-cgroup"
    own.write_text(f"0::{plan.cgroup}\n")
    tree = tmp_path / "model"
    tree.mkdir()
    (tree / "sessions").mkdir()
    return (
        tree,
        CgroupReader(plan, controller_pid=1234, cgroup_root=root, self_cgroup=own),
        group,
    )


def finish(window: ForkObservation, tree: Path) -> dict[str, object]:
    window.seal_terminal()
    shutil.rmtree(tree)
    window.check_deleted()
    return window.receipt()


def test_full_fixture_window_keeps_history_terminal_and_deletion_distinct(
    tmp_path: Path,
) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        transient = tree / "sessions" / "fixed-sentinel"
        transient.write_bytes(b"synthetic")
        transient.unlink()
        window._observer.ingest(struct.pack("iIII", 1, 0x100, 0, 0))
        result = finish(window, tree)
    assert result["source"] == "synthetic_cgroup_fixture"
    assert result["result"] == "window_complete"
    assert result["history"] == "observed_mutation"
    assert result["terminal_regular_files"] == 0
    assert result["directory_deleted"] is True
    assert "fixed-sentinel" not in str(result)


def test_zero_history_does_not_mean_terminal_empty(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    (tree / "preexisting").write_bytes(b"synthetic")
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        result = finish(window, tree)
    assert result["result"] == "window_complete"
    assert result["history"] == "zero_observed"
    assert result["terminal_regular_files"] == 1


@pytest.mark.parametrize("members", ["1234\n4321\n", "4321\n", ""])
def test_dead_controller_or_remaining_child_cannot_close(
    tmp_path: Path, members: str
) -> None:
    tree, reader, group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        (group / "cgroup.procs").write_text(members)
        with pytest.raises(WindowRejected, match=r"^writers_not_quiescent$"):
            window.seal_terminal()
        receipt = window.receipt()
    assert receipt["result"] == "unknown"
    assert receipt["history"] == "unknown"
    assert receipt["terminal_regular_files"] is None


def test_remaining_descendant_in_subgroup_prevents_terminal(tmp_path: Path) -> None:
    tree, reader, group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        child = group / "child"
        child.mkdir()
        (child / "cgroup.procs").write_text("4321\n")
        with pytest.raises(WindowRejected, match=r"^writers_not_quiescent$"):
            window.seal_terminal()
        assert window.receipt()["result"] == "unknown"


def test_missing_cgroup_is_not_trusted_as_empty(tmp_path: Path) -> None:
    tree, reader, group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        shutil.rmtree(group)
        with pytest.raises(WindowRejected, match=r"^cgroup_read_unknown$"):
            window.seal_terminal()
        assert window.receipt()["result"] == "unknown"


def test_recreated_cgroup_identity_is_unknown(tmp_path: Path) -> None:
    tree, reader, group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        moved = group.with_name("old-group")
        group.rename(moved)
        group.mkdir()
        (group / "cgroup.procs").write_text("1234\n")
        with pytest.raises(WindowRejected, match=r"^cgroup_identity_unknown$"):
            window.seal_terminal()
        assert window.receipt()["result"] == "unknown"


def test_self_membership_mismatch_blocks_start(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    reader.self_cgroup.write_text("0::/different-group\n")
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        with pytest.raises(WindowRejected, match=r"^self_cgroup_unknown$"):
            window.start()
        assert window.receipt()["result"] == "unknown"


@pytest.mark.parametrize("operation", ["start", "terminal", "delete"])
def test_missing_lifecycle_stays_unknown(tmp_path: Path, operation: str) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        if operation != "start":
            window.start()
        if operation == "delete":
            window.seal_terminal()
        result = window.receipt()
    assert result["result"] == "unknown"
    assert "complete_lifecycle_missing" in cast(list[str], result["reasons"])


def test_overflow_preserves_unknown_despite_successful_snapshot(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        window._observer.ingest(struct.pack("iIII", -1, 0x4000, 0, 0))
        result = finish(window, tree)
    assert result["result"] == "unknown"
    assert result["history"] == "unknown"
    assert result["terminal_regular_files"] == 0
    assert result["directory_deleted"] is True


def test_new_directory_window_is_not_promoted_to_complete(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        (tree / "late-directory").mkdir()
        window._observer.ingest(struct.pack("iIII", 1, 0x40000100, 0, 0))
        result = finish(window, tree)
    assert result["result"] == "unknown"
    assert result["history"] == "unknown"


def test_child_reappearing_after_snapshot_invalidates_cleanup(tmp_path: Path) -> None:
    tree, reader, group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        window.seal_terminal()
        shutil.rmtree(tree)
        (group / "cgroup.procs").write_text("1234\n4321\n")
        with pytest.raises(WindowRejected, match=r"^writers_not_quiescent$"):
            window.check_deleted()
        result = window.receipt()
    assert result["result"] == "unknown"
    assert result["directory_deleted"] is True
    assert result["terminal_regular_files"] == 0


def test_post_terminal_mutation_is_not_hidden_as_normal_cleanup(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        window.seal_terminal()
        window._observer.ingest(struct.pack("iIII", 1, 0x2, 0, 0))
        shutil.rmtree(tree)
        window.check_deleted()
        result = window.receipt()
    assert result["result"] == "unknown"
    assert "cleanup_mutation_unknown" in cast(list[str], result["reasons"])


def test_post_terminal_overflow_cannot_be_hidden_as_normal_removal(
    tmp_path: Path,
) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        window.seal_terminal()
        window._observer.ingest(struct.pack("iIII", -1, 0x4000, 0, 0))
        shutil.rmtree(tree)
        window.check_deleted()
        result = window.receipt()
    assert result["result"] == "unknown"
    assert "cleanup_observation_unknown" in cast(list[str], result["reasons"])


def test_normal_ignored_event_after_removal_does_not_invalidate_history(
    tmp_path: Path,
) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        window.seal_terminal()
        shutil.rmtree(tree)
        window._observer.ingest(struct.pack("iIII", 1, 0x8000, 0, 0))
        window.check_deleted()
        result = window.receipt()
    assert result["result"] == "window_complete"


def test_unavailable_observer_raises_closed_reason(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)

    def unavailable(_root: Path) -> FileObserver:
        raise OSError("external-private-error-text")

    with pytest.raises(WindowRejected, match=r"^file_observer_unavailable$"):
        ForkObservation(tree, reader, observer_factory=unavailable)


def test_deletion_check_cannot_precede_actual_deletion(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        window.seal_terminal()
        with pytest.raises(WindowRejected, match=r"^deletion_unknown$"):
            window.check_deleted()
        shutil.rmtree(tree)
        assert window.receipt()["result"] == "unknown"


def test_writer_after_deletion_check_is_not_hidden_in_receipt(tmp_path: Path) -> None:
    tree, reader, group = fixture(tmp_path)
    with ForkObservation(tree, reader, observer_factory=ReplayObserver) as window:
        window.start()
        window.seal_terminal()
        shutil.rmtree(tree)
        window.check_deleted()
        (group / "cgroup.procs").write_text("1234\n4321\n")
        result = window.receipt()
    assert result["result"] == "unknown"
    assert "writers_not_quiescent" in cast(list[str], result["reasons"])
