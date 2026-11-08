"""Independent D1: S classification, own temporary files/inotify only."""

import json
import os
import shutil
import struct
from pathlib import Path
from typing import Any, cast

import pytest

from paper_radar.pi_execution.resources import SETTINGS_JSON
from scripts.issue167_fork_observation import CgroupReader
from scripts.issue167_h1_phase import Plan
from scripts.issue167_session_observation import (
    ClassifiedSessionObservation,
    SessionObservationRejected,
)


@pytest.fixture
def reader(tmp_path: Path) -> CgroupReader:
    plan = Plan("ab7812345678", os.getuid(), os.getgid(), network_mode="ipv4_only")
    cg = tmp_path / "fixture-cgroup"
    group = cg / "system.slice" / plan.unit
    group.mkdir(parents=True)
    (group / "cgroup.procs").write_text(f"{os.getpid()}\n")
    own = tmp_path / "fixture-self"
    own.write_text(f"0::{plan.cgroup}\n")
    return CgroupReader(plan, cgroup_root=cg, self_cgroup=own)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "model"
    root.mkdir()
    for name in ("home", "tmp", "agent"):
        (root / name).mkdir()
    (root / "agent/settings.json").write_bytes(SETTINGS_JSON)
    return root


def public_window(root: Path, reader: CgroupReader) -> ClassifiedSessionObservation:
    return ClassifiedSessionObservation(root, reader, expected_settings=SETTINGS_JSON)


def receipt(window: ClassifiedSessionObservation) -> dict[str, Any]:
    return cast(dict[str, Any], window.receipt())


def finish(window: ClassifiedSessionObservation, tree: Path) -> dict[str, Any]:
    window.seal_terminal()
    window.ready_for_delete()
    shutil.rmtree(tree)
    window.check_deleted()
    return receipt(window)


def test_known_stores_locks_and_nested_compile_cache_are_not_session_zero_claims(
    tree: Path,
    reader: CgroupReader,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        for name in ("auth.json", "models-store.json"):
            (tree / "agent" / name).write_bytes(b"{}")
        for name in ("auth.json", "models-store.json", "settings.json"):
            lock = tree / "agent" / f"{name}.lock"
            lock.mkdir()
            lock.rmdir()
        cache = tree / "tmp/node-compile-cache/v-fixed/deep"
        cache.mkdir(parents=True)
        (cache / "nonsecret-bytecode").write_bytes(b"fixed-public-code")
        row = finish(window, tree)
    assert row["result"] == "session_window_complete"
    assert row["session_history"] == "zero_observed"
    assert row["session_integrity"] == "complete"
    assert row["known_non_session_history"] == "not_assessed"
    assert row["terminal_inventory"]["compile_cache"]["regular"] == 1
    assert row["terminal_inventory"]["baseline"] == {
        "regular": 1,
        "directory": 3,
        "other": 0,
    }
    assert row["directory_deleted"] is True
    assert "nonsecret-bytecode" not in str(row)


def test_same_false_rpc_controls_may_rewrite_public_settings_format(
    tree: Path,
    reader: CgroupReader,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        data = json.loads(SETTINGS_JSON)
        data["retry"]["enabled"] = False
        (tree / "agent/settings.json").write_text(json.dumps(data, indent=2))
        data["compaction"]["enabled"] = False
        (tree / "agent/settings.json").write_text(json.dumps(data, sort_keys=False))
        row = finish(window, tree)
    assert row["result"] == "session_window_complete"
    assert row["settings_semantics"] is True
    assert row["non_session_event_lower_bounds"]["control_settings"] > 0


def test_short_lived_session_is_observed_even_when_terminal_entry_is_gone(
    tree: Path,
    reader: CgroupReader,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        sessions = tree / "agent/sessions"
        sessions.mkdir()
        transient = sessions / "never-persist-this-name.jsonl"
        transient.write_bytes(b"synthetic-session")
        transient.unlink()
        sessions.rmdir()
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        row = receipt(window)
    assert tree.exists()
    assert row["session_history"] == "observed_mutation"
    assert row["session_mutation_events"] > 0
    assert row["terminal_inventory"]["session"]["regular"] == 0


@pytest.mark.parametrize("relative", ["tmp/unknown", "home/.pi", "agent/settings.json"])
def test_unknown_or_baseline_write_blocks_without_reading_contents(
    tree: Path,
    reader: CgroupReader,
    relative: str,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        (tree / relative).write_bytes(b"private-test-value-not-read")
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        row = receipt(window)
    assert row["result"] == "unknown"
    if relative == "agent/settings.json":
        assert row["settings_semantics"] is False
        assert row["non_session_event_lower_bounds"]["control_settings"] > 0
    else:
        assert row["unknown_mutation_events"] > 0
    assert "private-test-value" not in str(row)


@pytest.mark.parametrize(
    "mask,descriptor", [(0x4000, -1), (0x2000, 1), (0x8000, 1), (0x2, 999999)]
)
def test_overflow_missing_watch_and_coverage_loss_are_never_zero(
    tree: Path,
    reader: CgroupReader,
    mask: int,
    descriptor: int,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        if descriptor == 1:
            descriptor = window._paths[tree]
        window.ingest(struct.pack("iIII", descriptor, mask, 0, 0))
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        assert receipt(window)["guard_integrity"] == "unknown"


def test_cache_boundary_move_is_not_an_allowed_cache_write(
    tree: Path, reader: CgroupReader
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        cache = tree / "tmp/node-compile-cache"
        cache.mkdir()
        cache.rename(tree / "home/moved-cache")
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_terminal_aliases_or_special_files_block(
    tree: Path, reader: CgroupReader, kind: str
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        cache = tree / "tmp/node-compile-cache"
        cache.mkdir()
        target = cache / "alias"
        if kind == "symlink":
            target.symlink_to(tree / "agent/settings.json")
        elif kind == "hardlink":
            os.link(tree / "agent/settings.json", target)
        else:
            os.mkfifo(target)
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        assert receipt(window)["terminal_integrity"] == "unknown"


def test_terminal_compile_cache_boundary_cannot_be_a_regular_file(
    tree: Path,
    reader: CgroupReader,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        (tree / "tmp/node-compile-cache").write_bytes(b"not-a-directory")
        window.seal_terminal()
        assert receipt(window)["terminal_integrity"] == "unknown"


def test_event_limit_is_unknown_not_silent_truncation(
    tree: Path,
    reader: CgroupReader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import issue167_session_observation as module

    monkeypatch.setattr(module, "MAX_EVENTS", 2)
    with public_window(tree, reader) as window:
        window.start()
        event = struct.pack(
            "iIII", window._paths[tree / "agent"], 0x100, 0, 16
        ) + b"auth.json\0".ljust(16, b"\0")
        window.ingest(event * 3)
        window.seal_terminal()
        row = receipt(window)
    assert row["guard_integrity"] == "unknown"
    assert "event_record_limit_unknown" in row["reasons"]


BAD_SETTINGS = (
    SETTINGS_JSON.replace(b"false", b"true", 1),
    SETTINGS_JSON.replace(b"false", b"0", 1),
    SETTINGS_JSON.replace(b'"maxRetries":0', b'"maxRetries":false'),
    SETTINGS_JSON.replace(b'"maxRetries":0', b'"maxRetries":NaN'),
    SETTINGS_JSON.rstrip()[:-1] + b',"retry":{"enabled":false}}',
    json.dumps(
        {**json.loads(SETTINGS_JSON), "apiKey": "synthetic-public-not-secret"}
    ).encode(),
    b"{",
)


@pytest.mark.parametrize("raw", BAD_SETTINGS)
def test_public_settings_semantic_drift_is_unknown(
    tree: Path,
    reader: CgroupReader,
    raw: bytes,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        (tree / "agent/settings.json").write_bytes(raw)
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        row = receipt(window)
    assert row["settings_semantics"] is False
    assert row["guard_integrity"] == "unknown"
    assert row["result"] == "unknown"
    assert "synthetic-public-not-secret" not in str(row)


@pytest.mark.parametrize("raw", BAD_SETTINGS)
def test_wrong_public_reference_cannot_bless_existing_settings(
    tree: Path,
    reader: CgroupReader,
    raw: bytes,
) -> None:
    (tree / "agent/settings.json").write_bytes(raw)
    with pytest.raises(
        SessionObservationRejected, match="public_settings_reference_unknown"
    ):
        ClassifiedSessionObservation(tree, reader, expected_settings=raw)


def test_missing_public_reference_is_not_read_from_actual_file(
    tree: Path,
    reader: CgroupReader,
) -> None:
    with pytest.raises(
        SessionObservationRejected, match="public_settings_reference_missing"
    ):
        ClassifiedSessionObservation(tree, reader)


def test_initial_file_cannot_override_the_explicit_public_reference(
    tree: Path,
    reader: CgroupReader,
) -> None:
    (tree / "agent/settings.json").write_bytes(
        SETTINGS_JSON.replace(b"false", b"true", 1)
    )
    with pytest.raises(
        SessionObservationRejected, match="session_observer_unavailable"
    ):
        public_window(tree, reader)


@pytest.mark.parametrize("change", ["attrs", "replace"])
def test_settings_identity_changes_are_not_control_rewrites(
    tree: Path,
    reader: CgroupReader,
    change: str,
    tmp_path: Path,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        path = tree / "agent/settings.json"
        if change == "attrs":
            previous = path.stat().st_mode & 0o777
            path.chmod(0o400)
            path.chmod(previous)
        else:
            replacement = tmp_path / "replacement"
            replacement.write_bytes(SETTINGS_JSON)
            replacement.replace(path)
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        assert receipt(window)["guard_integrity"] == "unknown"


def test_file_watch_catches_baseline_write_through_unwatched_cache_alias(
    tree: Path,
    reader: CgroupReader,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        cache = tree / "tmp/node-compile-cache"
        cache.mkdir()
        alias = cache / "alias"
        os.link(tree / "agent/settings.json", alias)
        alias.write_bytes(b"changed-with-alias")
        alias.unlink()
        window.seal_terminal()
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        assert receipt(window)["unknown_mutation_events"] > 0


def test_new_session_and_cache_mixed_stays_blocked(
    tree: Path, reader: CgroupReader
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        (tree / "agent/auth.json").write_bytes(b"{}")
        (tree / "agent/sessions").mkdir()
        window.seal_terminal()
        row = receipt(window)
    assert row["non_session_event_lower_bounds"]["auth_store"] > 0
    assert row["session_mutation_events"] > 0
    assert row["result"] == "unknown"


def test_post_terminal_write_cannot_be_hidden_by_cleanup(
    tree: Path, reader: CgroupReader
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        (tree / "agent/auth.json").write_bytes(b"{}")
        window.seal_terminal()
        (tree / "agent/auth.json").write_bytes(b"post-terminal-change")
        shutil.rmtree(tree)
        window.check_deleted()
        row = receipt(window)
    assert row["directory_deleted"] is True
    assert row["cleanup_integrity"] == "unknown"
    assert row["post_terminal_write_events"] > 0


def test_cgroup_writers_block_seal_and_directory_deletion_is_independent(
    tree: Path,
    reader: CgroupReader,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        group = reader.cgroup_root / "system.slice" / reader.plan.unit / "cgroup.procs"
        group.write_text(f"{os.getpid()}\n{os.getpid() + 100000}\n")
        with pytest.raises(SessionObservationRejected, match="writers_not_quiescent"):
            window.seal_terminal()
        group.write_text(f"{os.getpid()}\n")
        assert tree.exists()
        assert receipt(window)["result"] == "unknown"


def test_complete_terminal_does_not_prove_directory_deleted(
    tree: Path, reader: CgroupReader
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        window.seal_terminal()
        window.ready_for_delete()
        row = receipt(window)
        assert row["terminal_integrity"] == "complete"
        assert row["directory_deleted"] is False
        assert row["result"] == "unknown"
        shutil.rmtree(tree)
        window.check_deleted()
        assert receipt(window)["result"] == "session_window_complete"


@pytest.mark.parametrize(
    "payload",
    [b"short", struct.pack("iIII", 1, 0x100, 0, 4096), struct.pack("iIII", 1, 0, 0, 0)],
)
def test_malformed_records_do_not_hide_observation_failure(
    tree: Path,
    reader: CgroupReader,
    payload: bytes,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        window.ingest(payload)
        window.seal_terminal()
        assert receipt(window)["guard_integrity"] == "unknown"


def test_watch_fd_is_not_inheritable_and_close_failure_revokes_result(
    tree: Path,
    reader: CgroupReader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = public_window(tree, reader)
    assert not os.get_inheritable(window.fd)
    window.start()
    assert finish(window, tree)["result"] == "session_window_complete"
    real_close = os.close
    descriptor = window.fd

    def broken_close(fd: int) -> None:
        if fd == descriptor:
            raise OSError("synthetic-close-failure")
        real_close(fd)

    monkeypatch.setattr(os, "close", broken_close)
    try:
        with pytest.raises(OSError, match="synthetic-close-failure"):
            window.close()
        assert receipt(window)["result"] == "unknown"
    finally:
        real_close(descriptor)


@pytest.mark.parametrize("authorized", [False, True])
def test_watch_removed_after_terminal_cannot_hide_a_cleanup_session_write(
    tree: Path,
    reader: CgroupReader,
    authorized: bool,
) -> None:
    with public_window(tree, reader) as window:
        window.start()
        window.seal_terminal()
        if authorized:
            window.ready_for_delete()
        assert (
            window._libc.inotify_rm_watch(window.fd, window._paths[tree / "agent"]) == 0
        )
        window.drain()
        session = tree / "agent/sessions"
        session.mkdir()
        (session / "unreported.jsonl").write_bytes(b"synthetic-session")
        with pytest.raises(
            SessionObservationRejected, match="session_observation_unknown"
        ):
            window.ready_for_delete()
        shutil.rmtree(tree)
        window.check_deleted()
        row = receipt(window)
    assert row["result"] == "unknown"
    assert row["guard_integrity"] == "unknown"
    assert row["cleanup_integrity"] == "unknown"
