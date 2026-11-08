"""Independent D1 kernel prerequisite; an unavailable watch is a real failure."""

import shutil
from pathlib import Path

from scripts.issue167_fork_observation import ForkObservation
from scripts.issue167_observation import FileObserver
from tests.test_issue167_fork_observation import fixture


def test_kernel_can_watch_a_new_empty_synthetic_tree(tmp_path: Path) -> None:
    # No processes, network, credentials, mutations, or cgroup claims. This must
    # fail rather than skip/replay when the host cannot allocate a real watch.
    with FileObserver(tmp_path) as observer:
        assert observer.fd >= 0


def test_kernel_events_preserve_transient_history_with_fixture_membership(
    tmp_path: Path,
) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader) as window:
        window.start()
        transient = tree / "sessions" / "synthetic-event"
        transient.write_bytes(b"fixed-nonsecret")
        transient.unlink()
        window.seal_terminal()
        shutil.rmtree(tree)
        window.check_deleted()
        receipt = window.receipt()
    assert receipt["source"] == "synthetic_cgroup_fixture"
    assert receipt["event_source"] == "inotify"
    assert receipt["result"] == "window_complete"
    assert receipt["history"] == "observed_mutation"
    assert receipt["terminal_regular_files"] == 0
    assert receipt["directory_deleted"] is True


def test_kernel_events_keep_preexisting_terminal_file_separate(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    (tree / "preexisting").write_bytes(b"fixed-nonsecret")
    with ForkObservation(tree, reader) as window:
        window.start()
        window.seal_terminal()
        shutil.rmtree(tree)
        window.check_deleted()
        receipt = window.receipt()
    assert receipt["result"] == "window_complete"
    assert receipt["history"] == "zero_observed"
    assert receipt["terminal_regular_files"] == 1
    assert receipt["directory_deleted"] is True


def test_kernel_post_terminal_write_stays_unknown(tmp_path: Path) -> None:
    tree, reader, _group = fixture(tmp_path)
    with ForkObservation(tree, reader) as window:
        window.start()
        window.seal_terminal()
        unexpected = tree / "post-terminal"
        unexpected.write_bytes(b"fixed-nonsecret")
        unexpected.unlink()
        shutil.rmtree(tree)
        window.check_deleted()
        receipt = window.receipt()
    assert receipt["source"] == "synthetic_cgroup_fixture"
    assert receipt["event_source"] == "inotify"
    assert receipt["result"] == "unknown"
    reasons = receipt["reasons"]
    assert isinstance(reasons, list)
    assert "cleanup_mutation_unknown" in reasons
