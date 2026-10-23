"""Screening 任务公共边界;预读不可变输入,短写事务复核论文事实。"""

import re
import sqlite3
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from paper_radar.config import ConfigError, load_config_snapshot
from paper_radar.papers import PaperError, PaperFacts, resolve_revision
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.frozen import load_frozen
from paper_radar.screening_tasks.models import FrozenInput, RequestReceipt, ValueRequest
from paper_radar.screening_tasks.repository import (
    evidence_values,
    receipt_row,
    register_request,
    replay_request,
    to_receipt,
)
from paper_radar.screening_tasks.rules import parse_request
from paper_radar.screening_tasks.tables import budgets, requests, tasks
from paper_radar.stage_inputs import BuildReason, StageInputError
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.schema import runtime_config_snapshots


def database_error(error: SQLAlchemyError) -> TaskError:
    busy = (
        isinstance(error, DBAPIError)
        and isinstance(error.orig, sqlite3.Error)
        and (getattr(error.orig, "sqlite_errorcode", 0) & 0xFF) == sqlite3.SQLITE_BUSY
    )
    return TaskError(TaskReason.DATABASE_BUSY if busy else TaskReason.CORRUPT_REFERENCE)


class ScreeningTasks:
    def __init__(self, database: Path, data_root: Path | None = None) -> None:
        self.database = database
        self.data_root = data_root

    def register(self, raw_request: object) -> RequestReceipt:
        request = parse_request(raw_request)
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            # 精确 manual 重放先于当前映射,保留原回执即使论文已变化或缺项。
            with engine.connect() as connection:
                replayed = replay_request(connection, request)
                if replayed is not None:
                    return replayed
            mapping = PaperFacts(self.database).map_screening_inputs(
                paper_id=request.paper_id, snapshot_id=request.snapshot_id
            )
            mapped = mapping.boundary if request.stage == "boundary" else mapping.value
            if mapped.reason is not None:
                raise PaperError(mapped.reason)
            if mapped.value is None or mapped.evidence is None:
                raise TaskError(TaskReason.CORRUPT_REFERENCE)
            snapshot = load_config_snapshot(self.database, request.snapshot_id)
            if isinstance(request, ValueRequest):
                try:
                    mapped.value.value_prediction_context(
                        snapshot, original_title_is_zh=request.original_title_is_zh
                    )
                except StageInputError as error:
                    assert isinstance(error.reason, BuildReason)
                    raise TaskError(
                        TaskReason.INVALID_CONTEXT,
                        build_reason=error.reason,
                        field=error.field,
                    ) from None
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                # 并发另一登记可能已经完成相同 manual 请求,应重放其原回执。
                replayed = replay_request(connection, request)
                if replayed is not None:
                    return replayed
                current = resolve_revision(connection, paper_id=request.paper_id)
                if evidence_values(current) != evidence_values(mapped.evidence):
                    raise TaskError(TaskReason.FACTS_CHANGED)
                if (
                    connection.execute(
                        select(runtime_config_snapshots.c.snapshot_id).where(
                            runtime_config_snapshots.c.snapshot_id
                            == request.snapshot_id
                        )
                    ).first()
                    is None
                ):
                    raise TaskError(TaskReason.CORRUPT_REFERENCE)
                result = register_request(
                    connection, request, mapped.value, mapped.evidence
                )
                connection.commit()
                return result
        except SQLAlchemyError as error:
            raise database_error(error) from None
        finally:
            engine.dispose()

    def get_receipt(self, receipt_id: str) -> RequestReceipt:
        if (
            type(receipt_id) is not str
            or re.fullmatch(r"[0-9a-f]{64}", receipt_id) is None
        ):
            raise TaskError(TaskReason.REQUEST_NOT_FOUND)
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                row = receipt_row(connection, receipt_id)
                if row is None:
                    raise TaskError(TaskReason.REQUEST_NOT_FOUND)
                return to_receipt(row)
        except SQLAlchemyError as error:
            raise database_error(error) from None
        finally:
            engine.dispose()

    def receipts(self, paper_id: str) -> tuple[RequestReceipt, ...]:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                ids = (
                    connection.execute(
                        select(requests.c.receipt_id)
                        .join(tasks, requests.c.task_id == tasks.c.task_id)
                        .join(budgets, tasks.c.budget_id == budgets.c.budget_id)
                        .where(budgets.c.paper_id == paper_id)
                        .order_by(requests.c.receipt_id)
                    )
                    .scalars()
                    .all()
                )
                return tuple(
                    to_receipt(row)
                    for identifier in ids
                    if (row := receipt_row(connection, identifier)) is not None
                )
        except SQLAlchemyError as error:
            raise database_error(error) from None
        finally:
            engine.dispose()

    def load_input(self, receipt_id: str) -> FrozenInput:
        receipt = self.get_receipt(receipt_id)
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                budget = (
                    connection.execute(
                        select(budgets).where(budgets.c.budget_id == receipt.budget_id)
                    )
                    .mappings()
                    .one()
                )
                return load_frozen(self.database, connection, dict(budget))
        except (StageInputError, ConfigError, ValueError, TypeError, KeyError):
            raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
        except SQLAlchemyError as error:
            raise database_error(error) from None
        finally:
            engine.dispose()

    def validate_all(self) -> None:
        from paper_radar.screening_tasks.integrity import validate_registration

        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                validate_registration(self.database, connection)
        except SQLAlchemyError as error:
            raise database_error(error) from None
        except (
            StageInputError,
            ConfigError,
            PaperError,
            ValueError,
            TypeError,
            KeyError,
        ):
            raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
        finally:
            engine.dispose()
