"""Screening 任务公共边界;预读不可变输入,短写事务复核论文事实。"""

import re
from datetime import datetime
from pathlib import Path
from typing import overload

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.config import ConfigError, load_config_snapshot
from paper_radar.papers import PaperError, PaperFacts, resolve_revision
from paper_radar.screening_tasks.attempt_models import (
    Claim,
    Clock,
    FailureExecutor,
    FailureKind,
    FailureOrigin,
    FailureReceipt,
    FailureReport,
    TaskStatus,
    TestExecutor,
)
from paper_radar.screening_tasks.database_errors import database_error
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.execution import AttemptService
from paper_radar.screening_tasks.frozen import load_frozen
from paper_radar.screening_tasks.models import FrozenInput, RequestReceipt, ValueRequest
from paper_radar.screening_tasks.query import QueryService
from paper_radar.screening_tasks.query_models import TaskQueryResult
from paper_radar.screening_tasks.repository import (
    evidence_values,
    receipt_row,
    register_request,
    replay_request,
    to_receipt,
)
from paper_radar.screening_tasks.retry import RetryService
from paper_radar.screening_tasks.rules import parse_request
from paper_radar.screening_tasks.success import SuccessService
from paper_radar.screening_tasks.success_models import (
    SuccessCandidate,
    SuccessContent,
    SuccessReceipt,
    SuccessView,
)
from paper_radar.screening_tasks.tables import budgets, requests, tasks
from paper_radar.stage_inputs import BuildReason, StageInputError
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.schema import runtime_config_snapshots


class ScreeningTasks:
    def __init__(
        self,
        database: Path,
        data_root: Path | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.data_root = data_root
        self._attempts = AttemptService(database, clock)
        self._success = SuccessService(self._attempts, data_root)

    def query(self, *, paper_id: str, stage: str, snapshot_id: str) -> TaskQueryResult:
        return QueryService(self._attempts).query(
            paper_id=paper_id, stage=stage, snapshot_id=snapshot_id
        )

    def retry(self, raw_request: object) -> RequestReceipt:
        return RetryService(self._attempts).register(raw_request)

    def claim(self, receipt_id: str) -> Claim:
        return self._attempts.claim(
            self.get_receipt(receipt_id), self.load_input(receipt_id)
        )

    def status(self, receipt_id: str) -> TaskStatus:
        return self._attempts.status(self.get_receipt(receipt_id))

    def renew(self, handle: str) -> datetime:
        return self._attempts.renew(handle)

    def fail(self, claim: Claim, report: FailureReport) -> FailureReceipt:
        return self._attempts.fail(claim, report)

    def reclaim(self, receipt_id: str) -> TaskStatus:
        return self._attempts.reclaim(self.get_receipt(receipt_id))

    def submit(
        self, claim: Claim, candidate: SuccessCandidate
    ) -> SuccessReceipt | FailureReceipt:
        return self._success.submit(claim, candidate)

    def load_success(self, success_id: str) -> SuccessContent:
        return self._success.load(success_id)

    def query_successes(
        self, *, paper_id: str, stage: str, snapshot_id: str
    ) -> tuple[SuccessView, ...]:
        return self._success.query(
            paper_id=paper_id, stage=stage, snapshot_id=snapshot_id
        )

    @overload
    def run_once(
        self, receipt_id: str, executor: FailureExecutor
    ) -> FailureReceipt: ...

    @overload
    def run_once(
        self, receipt_id: str, executor: TestExecutor
    ) -> FailureReceipt | SuccessReceipt: ...

    def run_once(
        self, receipt_id: str, executor: TestExecutor
    ) -> FailureReceipt | SuccessReceipt:
        if not callable(executor):
            raise TaskError(TaskReason.INVALID_REQUEST)
        receipt = self.get_receipt(receipt_id)
        frozen = self.load_input(receipt_id)
        correction = self._attempts.correction(receipt)
        self._success.store().prepare_publish()
        claim = self._attempts.claim(receipt, frozen)
        stage_input = frozen.stage_input
        # claim 已提交;进程随后中断或执行者抛异常都不退还预算。
        origin: FailureOrigin = "executor"
        try:
            report = executor(stage_input, correction, claim.renewal_handle)
        except Exception:
            report = FailureReport(FailureKind.EXECUTOR_ERROR)
            origin = "exception"
        if type(report) is SuccessCandidate:
            try:
                return self.submit(claim, report)
            except TaskError as error:
                if error.reason != TaskReason.INVALID_CANDIDATE:
                    raise
            report = FailureReport(FailureKind.PROTOCOL_ERROR)
        if (
            type(report) is not FailureReport
            or type(report.kind) is not FailureKind
            or report.kind
            not in {
                FailureKind.TIMEOUT,
                FailureKind.CANCELLED,
                FailureKind.PROTOCOL_ERROR,
                FailureKind.EXECUTOR_ERROR,
            }
        ):
            # 未支持的返回只记录协议失败。
            report = FailureReport(FailureKind.PROTOCOL_ERROR)
        # 离开 except 后才结算,迟到结算的受控错误不串联原执行者异常。
        return self._attempts.fail(claim, report, origin=origin)

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
        from paper_radar.screening_tasks.attempt_integrity import validate_attempts
        from paper_radar.screening_tasks.integrity import validate_registration

        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                validate_registration(self.database, connection)
                validate_attempts(self.database, connection)
                from paper_radar.screening_tasks.success_integrity import (
                    validate_successes,
                )

                validate_successes(self._success, connection)
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
