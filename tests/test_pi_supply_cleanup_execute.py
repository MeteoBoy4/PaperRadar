"""公共执行边界:真实 SQLite、受控目录和内核保护。"""

import os
import select
from pathlib import Path

import pytest

from paper_radar.pi_supply import (
    SupplyError,
    acquire_install,
    activate_supply,
    probe_install,
)
from tests.pi_supply_process_support import inherited_child
from tests.pi_supply_support import SupplyRoots, inputs, prepare


@pytest.mark.parametrize("stage", ["retired", "completed"])
@pytest.mark.filterwarnings(
    "ignore:transaction already deassociated from connection:sqlalchemy.exc.SAWarning"
)
def test_interruption_after_progress_commit_keeps_replayable_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    import sqlite3

    from sqlalchemy.engine import RootTransaction

    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        list_cleanup_executions,
        rebuild_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=source[4],
    )
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    commit = RootTransaction.commit
    interrupted = False

    def interrupt_after_commit(connection: RootTransaction) -> None:
        nonlocal interrupted
        commit(connection)
        with sqlite3.connect(source[0]) as database:
            committed = database.execute(
                "SELECT COUNT(*) FROM pi_cleanup_progress WHERE phase=?", (stage,)
            ).fetchone()[0]
        if committed and not interrupted:
            interrupted = True
            raise KeyboardInterrupt

    with monkeypatch.context() as context:
        context.setattr(RootTransaction, "commit", interrupt_after_commit)
        with pytest.raises(KeyboardInterrupt):
            execute_cleanup_plan(source[0], plan.plan_id)
    execution = list_cleanup_executions(source[0])[0]
    if stage == "retired":
        assert [(i.phase, i.reason) for i in execution.items] == [
            ("failed", "operation_interrupted")
        ]
        assert [e.phase for e in execution.events] == ["not_run", "retired", "failed"]
        assert not execution.passed
    else:
        assert [(i.phase, i.reason) for i in execution.items] == [
            ("completed", "passed")
        ]
        assert execution.passed


@pytest.mark.parametrize("corruption", ["partial", "wrong_reason", "resume", "atomic"])
def test_batch_block_history_rejects_partial_or_resumed_events(
    tmp_path: Path, corruption: str
) -> None:
    import sqlite3

    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        list_cleanup_executions,
        rebuild_supply,
        show_cleanup_execution,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    for _ in range(2):
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    activate_supply(source[0], first.supply_id, source[1])
    if corruption == "atomic":
        with sqlite3.connect(source[0]) as database:
            database.execute(
                "CREATE TRIGGER reject_second_block BEFORE INSERT "
                "ON pi_cleanup_progress "
                "WHEN NEW.reason='cleanup_facts_changed' AND NEW.install_id='"
                + plan.candidates[1].install_id
                + "' BEGIN SELECT RAISE(ABORT, 'injected persistence failure'); END"
            )
        with pytest.raises(SupplyError, match="failure_record_failed"):
            execute_cleanup_plan(source[0], plan.plan_id)
        execution = list_cleanup_executions(source[0])[0]
        assert len(execution.events) == 2
        assert all(
            i.phase == "not_run" and i.reason == "not_run" for i in execution.items
        )
        return
    execution = execute_cleanup_plan(source[0], plan.plan_id)
    assert all(i.phase == "not_run" for i in execution.items)
    with sqlite3.connect(source[0]) as database:
        if corruption == "partial":
            database.execute(
                "DELETE FROM pi_cleanup_progress WHERE event_id=?",
                (execution.events[-1].event_id,),
            )
        elif corruption == "wrong_reason":
            database.execute(
                "UPDATE pi_cleanup_progress SET reason='tree_mismatch' "
                "WHERE event_id>?",
                (execution.events[1].event_id,),
            )
        else:
            database.execute(
                "INSERT INTO pi_cleanup_progress"
                "(run_id,install_id,phase,reason,created_at) "
                "VALUES(?,?,'failed','cleanup_failed',?)",
                (
                    execution.run_id,
                    execution.items[0].install_id,
                    execution.events[-1].created_at,
                ),
            )
    with pytest.raises(SupplyError, match="cleanup_history_invalid"):
        show_cleanup_execution(source[0], execution.run_id)


@pytest.mark.parametrize("drift", ["tree", "facts"])
def test_preflight_failure_identifies_item_or_blocks_whole_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    import fcntl

    from paper_radar.backup import create_backup, restore_backup
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        rebuild_supply,
        show_cleanup_execution,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    for _ in range(2):
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    assert len(plan.candidates) == 2
    original = fcntl.flock
    acquired = 0

    def lock(fd: int, operation: int) -> None:
        nonlocal acquired
        original(fd, operation)
        if operation & fcntl.LOCK_EX:
            acquired += 1
            if acquired == 2:
                if drift == "tree":
                    item = plan.candidates[0]
                    path = Path(item.root_path) / item.relative_path / "node/bin/node"
                    path.chmod(0o755)
                    path.write_bytes(b"changed during group lock acquisition")
                else:
                    activate_supply(source[0], first.supply_id, source[1])

    # The OS lock boundary controls a real change between the two preflight passes.
    with monkeypatch.context() as context:
        context.setattr(fcntl, "flock", lock)
        result = execute_cleanup_plan(source[0], plan.plan_id)
    assert not result.passed
    if drift == "tree":
        assert [(i.phase, i.reason) for i in result.items] == [
            ("failed", "cleanup_tree_changed"),
            ("not_run", "not_run"),
        ]
    else:
        assert [(i.phase, i.reason) for i in result.items] == [
            ("not_run", "cleanup_facts_changed"),
            ("not_run", "cleanup_facts_changed"),
        ]
    assert all((Path(i.root_path) / i.relative_path).exists() for i in plan.candidates)
    batch = create_backup(source[0], tmp_path / "data", tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    (tmp_path / "install").rename(tmp_path / "unavailable-root")
    assert (
        show_cleanup_execution(restored.target_dir / "database.sqlite3", result.run_id)
        == result
    )


def test_missing_registered_lock_cannot_bypass_child_holding_old_inode(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    activate_supply(source[0], first.supply_id, source[1])
    lock = tmp_path / "install/.locks" / f"{first.install_id}.lock"
    with inherited_child(source[0], source[1]) as (parent, child, release, _, _):
        death = os.pidfd_open(child)
        try:
            parent.kill()
            assert parent.wait(timeout=10) < 0
            lock.unlink()
            assert (
                probe_install(source[0], first.supply_id, first.install_id).state
                == "unknown"
            )
            with (
                pytest.raises(SupplyError, match="protection_unknown"),
                acquire_install(source[0], first.supply_id, first.install_id),
            ):
                pytest.fail("missing lock cannot be recreated while old fd lives")
            assert not lock.exists()
            os.write(release, b"X")
            assert select.select([death], [], [], 10)[0]
        finally:
            os.close(death)


@pytest.mark.parametrize("special", ["\t", "\n", "\\", " "])
def test_cleanup_refuses_network_mount_with_escaped_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, special: str
) -> None:
    from paper_radar.pi_supply import create_cleanup_plan

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    root = tmp_path / f"network{special}root"
    # mountinfo is the OS boundary: preserve real FS/DB and synthesize mount metadata.
    original = Path.read_text
    escaped = (
        str(root)
        .replace("\\", r"\134")
        .replace("\t", r"\011")
        .replace("\n", r"\012")
        .replace(" ", r"\040")
    )
    mountinfo = (
        f"1 0 0:1 / / rw - ext4 local rw\n2 1 0:2 / {escaped} rw - nfs host rw\n"
    )

    def read(path: Path, *args: object, **kwargs: object) -> str:
        if path == Path("/proc/self/mountinfo"):
            return mountinfo
        return original(path)

    monkeypatch.setattr(Path, "read_text", read)
    from paper_radar.pi_supply import rebuild_supply

    with pytest.raises(SupplyError, match="filesystem_unsupported"):
        rebuild_supply(
            source[0],
            first.supply_id,
            root,
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
    assert (
        create_cleanup_plan(
            source[0],
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
        ).candidates
        == ()
    )


def test_cleanup_refuses_ambiguous_same_mountpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_supply import rebuild_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    root = tmp_path / "network"
    original = Path.read_text
    mountinfo = (
        "1 0 0:1 / / rw - ext4 local rw\n"
        f"2 1 0:2 / {root} rw - nfs host rw\n"
        f"3 1 0:3 / {root} rw - tmpfs local rw\n"
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, *a, **k: (
            mountinfo if path == Path("/proc/self/mountinfo") else original(path)
        ),
    )
    with pytest.raises(SupplyError, match="filesystem_unsupported"):
        rebuild_supply(
            source[0],
            first.supply_id,
            root,
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )


def test_execute_collects_multiple_candidates_and_keeps_all_supply_history(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import (
        available_installs,
        create_cleanup_plan,
        execute_cleanup_plan,
        rebuild_supply,
        show_cleanup_execution,
        show_cleanup_plan,
        show_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    for _ in range(2):
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
    before = show_supply(source[0], first.supply_id)
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    assert len(plan.candidates) == 2
    result = execute_cleanup_plan(source[0], plan.plan_id)
    assert result.passed
    assert [item.phase for item in result.items] == ["completed", "completed"]
    assert show_cleanup_execution(source[0], result.run_id) == result
    assert (
        show_cleanup_plan(source[0], plan.plan_id).canonical_bytes
        == plan.canonical_bytes
    )
    assert show_supply(source[0], first.supply_id) == before
    assert len(available_installs(source[0], first.supply_id)) == 1
    for candidate in plan.candidates:
        assert not (Path(candidate.root_path) / candidate.relative_path).exists()
        with (
            pytest.raises(SupplyError, match="install_unavailable"),
            acquire_install(source[0], candidate.supply_id, candidate.install_id),
        ):
            pytest.fail("retirement is permanent")


def test_changed_facts_or_actual_tree_never_refresh_old_plan(tmp_path: Path) -> None:
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        rebuild_supply,
        show_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=source[4],
    )
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    plan = create_cleanup_plan(source[0], **roots)
    original = next(
        i.path
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    node = original / "node/bin/node"
    node.chmod(0o755)
    node.write_bytes(b"content changed after planning")
    rejected = execute_cleanup_plan(source[0], plan.plan_id)
    assert not rejected.passed and rejected.items[0].reason == "cleanup_tree_changed"
    assert original.is_dir()
    fresh = create_cleanup_plan(source[0], **roots)
    assert (
        fresh.candidates[0].actual_tree_hash != fresh.candidates[0].expected_tree_hash
    )
    activate_supply(source[0], first.supply_id, source[1])
    rejected = execute_cleanup_plan(source[0], fresh.plan_id)
    assert not rejected.passed and rejected.items[0].reason == "cleanup_facts_changed"
    assert original.is_dir()
    newest = create_cleanup_plan(source[0], **roots)
    assert execute_cleanup_plan(source[0], newest.plan_id).passed
    assert not original.exists()


def test_collection_restores_only_directories_and_preserves_external_hardlink(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        rebuild_supply,
        show_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=source[4],
    )
    path = next(
        i.path
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    outside = tmp_path / "hardlinked-sentinel"
    os.link(path / "node/bin/node", outside)
    mode, raw = outside.stat().st_mode, outside.read_bytes()
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    assert execute_cleanup_plan(source[0], plan.plan_id).passed
    assert outside.read_bytes() == raw and outside.stat().st_mode == mode
    assert not path.exists()


@pytest.mark.parametrize(
    "stage", ["retired", "renamed", "partial-2", "partial-4", "partial-6", "deleted"]
)
def test_real_kill_recovers_only_via_new_explicit_plan(
    tmp_path: Path, stage: str
) -> None:
    from paper_radar.pi_supply import (
        available_installs,
        create_cleanup_plan,
        execute_cleanup_plan,
        list_cleanup_executions,
        rebuild_supply,
        show_cleanup_plan,
        show_supply,
    )
    from tests.pi_cleanup_process_support import interrupted_execution

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=source[4],
    )
    path = next(
        i.path
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    path.chmod(0o755)
    (path / "a-ref").symlink_to("b-target")
    (path / "b-target").symlink_to("node/bin/node")
    (path / "directory-alias").symlink_to("node/bin", target_is_directory=True)
    (path / "through-prefix").symlink_to("directory-alias/node")
    path.chmod(0o555)
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    plan = create_cleanup_plan(source[0], **roots)
    assert len(plan.candidates) == 1
    original = show_supply(source[0], first.supply_id)
    with interrupted_execution(source[0], plan.plan_id, stage) as (process, _):
        process.kill()
        assert process.wait(timeout=10) < 0
    execution = list_cleanup_executions(source[0])[0]
    assert not execution.passed
    assert execution.items[0].phase in {"retired", "moved"}
    assert first.install_id not in {
        i.install_id for i in available_installs(source[0], first.supply_id)
    }
    with (
        pytest.raises(SupplyError, match="install_unavailable"),
        acquire_install(source[0], first.supply_id, first.install_id),
    ):
        pytest.fail("kill cannot restore retired availability")
    again = execute_cleanup_plan(source[0], plan.plan_id)
    assert not again.passed and again.items[0].reason == "cleanup_facts_changed"
    pending = create_cleanup_plan(source[0], **roots)
    if stage == "deleted":
        assert pending.retired_pending == () and pending.candidates == ()
        assert pending.items[0].disposition == "absent"
    else:
        assert len(pending.retired_pending) == 1 and len(pending.candidates) == 1
        assert pending.manual == ()
        assert pending.candidates[0].state == "retired_pending"
        assert execute_cleanup_plan(source[0], pending.plan_id).passed
    assert (
        not path.exists()
        and not (tmp_path / "install/.trash" / first.install_id).exists()
    )
    assert show_supply(source[0], first.supply_id) == original
    assert (
        show_cleanup_plan(source[0], plan.plan_id).canonical_bytes
        == plan.canonical_bytes
    )


@pytest.mark.parametrize("location", ["original", "trash"])
def test_completed_install_reappearance_is_unknown_not_a_retired_residual(
    tmp_path: Path, location: str
) -> None:
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        rebuild_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=source[4],
    )
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    plan = create_cleanup_plan(source[0], **roots)
    assert execute_cleanup_plan(source[0], plan.plan_id).passed
    path = (
        tmp_path
        / "install"
        / (first.supply_id if location == "original" else ".trash")
        / first.install_id
    )
    path.mkdir()
    sentinel = path / "unknown-material"
    sentinel.write_bytes(b"never collect a completed identity's replacement")
    rejected = execute_cleanup_plan(source[0], plan.plan_id)
    assert not rejected.passed and sentinel.exists()
    fresh = create_cleanup_plan(source[0], **roots)
    assert fresh.candidates == ()
    assert any(
        item.relative_path == path.relative_to(tmp_path / "install").as_posix()
        for item in fresh.manual
    )
    assert execute_cleanup_plan(source[0], fresh.plan_id).passed
    assert sentinel.read_bytes() == b"never collect a completed identity's replacement"


def test_old_plan_cannot_delete_after_parent_kill_while_child_holds_fd(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        list_cleanup_executions,
        rebuild_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=source[4],
    )
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    plan = create_cleanup_plan(source[0], **roots)
    assert len(plan.candidates) == 1
    with inherited_child(
        source[0], source[1], install=(first.supply_id, first.install_id)
    ) as (parent, child, release, _, _):
        death = os.pidfd_open(child)
        try:
            parent.kill()
            assert parent.wait(timeout=10) < 0
            result = execute_cleanup_plan(source[0], plan.plan_id)
            assert not result.passed and result.items[0].reason == "install_busy"
            assert all(event.phase != "retired" for event in result.events)
            protected = create_cleanup_plan(source[0], **roots)
            assert protected.candidates == ()
            assert protected.items[0].protection == ("in_flight",)
            os.write(release, b"X")
            assert select.select([death], [], [], 10)[0]
        finally:
            os.close(death)
    fresh = create_cleanup_plan(source[0], **roots)
    assert execute_cleanup_plan(source[0], fresh.plan_id).passed
    assert len(list_cleanup_executions(source[0])) == 2


def test_replaced_trash_directory_link_is_never_followed(tmp_path: Path) -> None:
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        list_cleanup_executions,
        rebuild_supply,
    )
    from tests.pi_cleanup_process_support import interrupted_execution

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=source[4],
    )
    plan = create_cleanup_plan(source[0], **roots)
    outside = tmp_path / "protected-materials"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_bytes(b"do not follow replaced directories")
    with interrupted_execution(source[0], plan.plan_id, "renamed") as (
        process,
        release,
    ):
        trash = tmp_path / "install/.trash" / first.install_id
        trash.rename(trash.parent / "unknown-residual")
        trash.symlink_to(outside, target_is_directory=True)
        os.write(release, b"X")
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0 and stdout.strip() == b"False" and not stderr
    result = list_cleanup_executions(source[0])[0]
    assert result.items[0].phase == "failed" and result.items[0].reason == "unsafe_path"
    assert sentinel.read_bytes() == b"do not follow replaced directories"
    fresh = create_cleanup_plan(source[0], **roots)
    assert fresh.candidates == () and fresh.items[0].disposition == "unverifiable"


def test_valid_link_can_traverse_same_directory_alias_twice(tmp_path: Path) -> None:
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        rebuild_supply,
        show_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=source[4],
    )
    path = next(
        i.path
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    path.chmod(0o755)
    (path / "directory-alias").symlink_to("node/bin", target_is_directory=True)
    (path / "revisit").symlink_to("directory-alias/../../directory-alias/node")
    plan = create_cleanup_plan(source[0], **roots)
    assert len(plan.candidates) == 1
    assert execute_cleanup_plan(source[0], plan.plan_id).passed


def test_real_install_with_many_directories_does_not_require_one_fd_per_directory(
    tmp_path: Path,
) -> None:
    import subprocess
    import sys

    from paper_radar.pi_supply import create_cleanup_plan, rebuild_supply, show_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=source[4],
    )
    path = next(
        i.path
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    path.chmod(0o755)
    for index in range(100):
        (path / f"package-{index}").mkdir()
    plan = create_cleanup_plan(source[0], **roots)
    code = """
import resource, sys
from pathlib import Path
from paper_radar.pi_supply import execute_cleanup_plan
hard = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
resource.setrlimit(resource.RLIMIT_NOFILE, (64, hard))
assert execute_cleanup_plan(Path(sys.argv[1]), sys.argv[2]).passed
"""
    result = subprocess.run(
        (sys.executable, "-c", code, str(source[0]), plan.plan_id),
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_rebuild_resume_cannot_recreate_missing_registered_lock(tmp_path: Path) -> None:
    from paper_radar.pi_supply import rebuild_supply
    from tests.pi_supply_support import encoded

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    pending = tmp_path / "install" / f".pending-rebuild-{first.supply_id}.json"
    pending.write_bytes(
        encoded({"supply_id": first.supply_id, "install_id": first.install_id})
    )
    lock = tmp_path / "install/.locks" / f"{first.install_id}.lock"
    with inherited_child(
        source[0], source[1], install=(first.supply_id, first.install_id)
    ) as (parent, child, release, _, _):
        death = os.pidfd_open(child)
        try:
            parent.kill()
            assert parent.wait(timeout=10) < 0
            lock.unlink()
            with pytest.raises(SupplyError, match="protection_unknown"):
                rebuild_supply(
                    source[0],
                    first.supply_id,
                    tmp_path / "install",
                    data_root=tmp_path / "data",
                    config_root=tmp_path / "config",
                    material_root=tmp_path / "materials",
                    downloader=source[3],
                    runner=source[4],
                )
            assert not lock.exists()
            os.write(release, b"X")
            assert select.select([death], [], [], 10)[0]
        finally:
            os.close(death)


def test_unregistered_existing_publication_target_with_missing_lock_is_unknown(
    tmp_path: Path,
) -> None:
    import shutil

    from paper_radar.pi_supply import rebuild_supply, show_supply
    from tests.pi_supply_support import encoded

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    instance = show_supply(source[0], first.supply_id).installs[0]
    install_id = "a" * 32
    target = instance.path.parent / install_id
    shutil.copytree(instance.path, target, symlinks=True)
    pending = tmp_path / "install" / f".pending-rebuild-{first.supply_id}.json"
    pending.write_bytes(
        encoded({"supply_id": first.supply_id, "install_id": install_id})
    )
    with pytest.raises(SupplyError, match="protection_unknown"):
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
    assert not (tmp_path / "install/.locks" / f"{install_id}.lock").exists()
    assert target.exists()


def test_damaged_empty_tree_without_execute_bit_keeps_planned_identity_until_move(
    tmp_path: Path,
) -> None:
    import shutil

    from paper_radar.pi_supply import (
        create_cleanup_plan,
        execute_cleanup_plan,
        rebuild_supply,
        show_supply,
    )

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=source[4],
    )
    path = next(
        i.path
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    path.chmod(0o755)
    for child in path.rglob("*"):
        if child.is_dir() and not child.is_symlink():
            child.chmod(0o755)
    shutil.rmtree(path)
    path.mkdir(mode=0o444)
    plan = create_cleanup_plan(source[0], **roots)
    assert len(plan.candidates) == 1
    assert plan.candidates[0].actual_tree_hash != plan.candidates[0].expected_tree_hash
    assert execute_cleanup_plan(source[0], plan.plan_id).passed
    assert not path.exists()
