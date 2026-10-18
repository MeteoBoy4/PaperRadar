"""保存计划的安全执行:整组非阻塞排他、短事务退役、受控移动和逐项审计。"""

from __future__ import annotations

import re
import uuid
from contextlib import ExitStack
from pathlib import Path
from typing import Literal

from pydantic import JsonValue
from sqlalchemy import Connection, insert, select

from paper_radar.pi_supply import tables
from paper_radar.pi_supply.cleanup import (
    check_cleanup_root,
    read_cleanup_facts,
    show_cleanup_plan,
)
from paper_radar.pi_supply.cleanup_delete import delete_tree, move_to_trash
from paper_radar.pi_supply.cleanup_history import (
    completed_installs,
    safety_facts,
    validate_execution_history,
    validate_plan_history,
)
from paper_radar.pi_supply.cleanup_models import (
    PREFLIGHT_REASONS,
    CleanupExecution,
    CleanupItem,
    CleanupPhase,
    CleanupPlan,
)
from paper_radar.pi_supply.errors import SupplyError, SupplyReason
from paper_radar.pi_supply.filesystem import no_symlink_components, tree_hash
from paper_radar.pi_supply.protection import (
    InstallUse,
    collection_path,
    exclusive_install,
)
from paper_radar.pi_supply.repository import database_engine, now, read_state


def _event(
    connection: Connection,
    run_id: str,
    install_id: str,
    phase: CleanupPhase,
    reason: SupplyReason | Literal["passed", "not_run"],
) -> None:
    connection.execute(
        insert(tables.cleanup_progress).values(
            run_id=run_id,
            install_id=install_id,
            phase=phase,
            reason=reason,
            created_at=now(),
        )
    )


def _record(
    database: Path,
    run_id: str,
    install_id: str,
    phase: CleanupPhase,
    reason: SupplyReason | Literal["passed", "not_run"] = "passed",
) -> None:
    with database_engine(database, write=True) as engine, engine.begin() as connection:
        _event(connection, run_id, install_id, phase, reason)


def _record_failure(
    database: Path, run_id: str, install_id: str | None, reason: SupplyReason
) -> None:
    try:
        with (
            database_engine(database, write=True) as engine,
            engine.begin() as connection,
        ):
            progress = connection.execute(
                select(tables.cleanup_progress)
                .where(tables.cleanup_progress.c.run_id == run_id)
                .order_by(tables.cleanup_progress.c.event_id)
            ).mappings()
            latest = {row["install_id"]: row for row in progress}
            for candidate, event in latest.items():
                phase = event["phase"]
                if install_id is not None and candidate != install_id:
                    continue
                if phase in {"completed", "failed"} or (
                    phase == "not_run" and event["reason"] != "not_run"
                ):
                    continue
                # A batch prerequisite has no failing installation. Keep unstarted
                # candidates unstarted, and persist the whole diagnosis atomically.
                if install_id is None:
                    blocked = (
                        reason if reason in PREFLIGHT_REASONS else "cleanup_failed"
                    )
                    _event(
                        connection,
                        run_id,
                        candidate,
                        "not_run" if phase == "not_run" else "failed",
                        blocked,
                    )
                else:
                    _event(connection, run_id, candidate, "failed", reason)
    except SupplyError:
        raise SupplyError("failure_record_failed", execution_reason=reason) from None


def _check_item(
    database: Path, plan: CleanupPlan, item: CleanupItem, handle: InstallUse
) -> Path:
    with database_engine(database) as engine, engine.connect() as connection:
        if item.install_id in completed_installs(connection):
            raise SupplyError("cleanup_tree_changed")
    root = handle.instance.root
    check_cleanup_root(
        database,
        root,
        item.root_id,
        Path(plan.data_root),
        Path(plan.config_root),
        Path(plan.material_root),
    )
    path = collection_path(database, handle.instance)
    if (
        str(root) != item.root_path
        or path.relative_to(root).as_posix() != item.relative_path
    ):
        raise SupplyError("cleanup_tree_changed")
    no_symlink_components(path)
    if tree_hash(path) != item.actual_tree_hash:
        raise SupplyError("cleanup_tree_changed")
    return path


def _assert_facts(
    current: dict[str, JsonValue], expected: dict[str, JsonValue]
) -> None:
    if current != expected:
        raise SupplyError("cleanup_facts_changed")


def execute_cleanup_plan(database: Path, plan_id: str) -> CleanupExecution:
    plan = show_cleanup_plan(database, plan_id)
    if not plan.candidates:
        _assert_facts(read_cleanup_facts(database), plan.facts)
    run_id = uuid.uuid4().hex
    with database_engine(database, write=True) as engine, engine.begin() as connection:
        connection.execute(
            insert(tables.cleanup_executions).values(
                run_id=run_id, plan_id=plan_id, created_at=now()
            )
        )
        for item in plan.candidates:
            _event(connection, run_id, item.install_id, "not_run", "not_run")
    if not plan.candidates:
        return show_cleanup_execution(database, run_id)
    active: CleanupItem | None = None
    try:
        with ExitStack() as locks:
            _assert_facts(read_cleanup_facts(database), plan.facts)
            handles = {}
            for item in plan.candidates:
                active = item
                handles[item.install_id] = locks.enter_context(
                    exclusive_install(database, item.supply_id, item.install_id)
                )
                _check_item(database, plan, item, handles[item.install_id])
            # Lock acquisition and expensive hashes never hold SQLite's writer lock.
            active = None
            _assert_facts(read_cleanup_facts(database), plan.facts)
            for item in plan.candidates:
                active = item
                _check_item(database, plan, item, handles[item.install_id])
            active = None
            with (
                database_engine(database, write=True) as engine,
                engine.connect() as connection,
            ):
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    _assert_facts(safety_facts(connection), plan.facts)
                    for item in plan.candidates:
                        if item.state == "installed":
                            connection.execute(
                                insert(tables.retirements).values(
                                    install_id=item.install_id,
                                    plan_id=plan_id,
                                    created_at=now(),
                                )
                            )
                        _event(connection, run_id, item.install_id, "retired", "passed")
                    expected = safety_facts(connection)
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
            # Only this transaction's precise retirement additions are accepted.
            for item in plan.candidates:
                active = item
                _assert_facts(read_cleanup_facts(database), expected)
                path = _check_item(database, plan, item, handles[item.install_id])
                assert item.actual_tree_hash is not None
                path = move_to_trash(
                    path, Path(item.root_path), item.install_id, item.actual_tree_hash
                )
                _record(database, run_id, item.install_id, "moved")
                _assert_facts(read_cleanup_facts(database), expected)
                check_cleanup_root(
                    database,
                    Path(item.root_path),
                    item.root_id,
                    Path(plan.data_root),
                    Path(plan.config_root),
                    Path(plan.material_root),
                )
                delete_tree(path, item.actual_tree_hash)
                _record(database, run_id, item.install_id, "completed")
    except (SupplyError, OSError) as error:
        _record_failure(
            database,
            run_id,
            active.install_id if active is not None else None,
            error.reason if isinstance(error, SupplyError) else "cleanup_failed",
        )
    except KeyboardInterrupt:
        _record_failure(
            database,
            run_id,
            active.install_id if active is not None else None,
            "operation_interrupted",
        )
        raise
    return show_cleanup_execution(database, run_id)


def list_cleanup_executions(database: Path) -> tuple[CleanupExecution, ...]:
    before = read_cleanup_facts(database)
    records = read_state(database)[0]
    with database_engine(database) as engine, engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")
        _assert_facts(safety_facts(connection), before)
        plans = validate_plan_history(
            [
                dict(row)
                for row in connection.execute(select(tables.cleanup_plans)).mappings()
            ],
            safety_facts(connection),
            records,
        )
        return validate_execution_history(
            [
                dict(row)
                for row in connection.execute(
                    select(tables.cleanup_executions)
                ).mappings()
            ],
            [
                dict(row)
                for row in connection.execute(
                    select(tables.cleanup_progress)
                ).mappings()
            ],
            plans,
            safety_facts(connection),
        )


def show_cleanup_execution(database: Path, run_id: str) -> CleanupExecution:
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise SupplyError("cleanup_execution_missing")
    for execution in list_cleanup_executions(database):
        if execution.run_id == run_id:
            return execution
    raise SupplyError("cleanup_execution_missing")
