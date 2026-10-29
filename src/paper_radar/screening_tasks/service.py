"""Screening 任务公共边界;预读不可变输入,短写事务复核论文事实。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, overload

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
from paper_radar.screening_tasks.attempt_rules import is_executor_failure
from paper_radar.screening_tasks.database_errors import database_error
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.execution import AttemptService
from paper_radar.screening_tasks.feed_gate import FeedGate
from paper_radar.screening_tasks.feed_gate import find as find_feed_gate
from paper_radar.screening_tasks.feed_gate import retain as retain_feed_gate
from paper_radar.screening_tasks.frozen import load_frozen
from paper_radar.screening_tasks.models import FrozenInput, RequestReceipt, ValueRequest
from paper_radar.screening_tasks.query import QueryService
from paper_radar.screening_tasks.query_models import TaskQueryResult
from paper_radar.screening_tasks.repository import (
    evidence_values,
    receipt_row,
    register_request,
    replay_request,
    require_stage_mapping,
    task_database,
    task_transaction,
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
from paper_radar.storage.database import require_current_revision
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
        # 先拒绝已有修正依据损坏;领取可能回收过期尝试,提交后需重读实际修正。
        self._attempts.correction(receipt)
        self._success.store().prepare_publish()
        claim = self._attempts.claim(receipt, frozen)
        stage_input = frozen.stage_input
        correction = self._attempts.correction(receipt)
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
        if not is_executor_failure(report):
            # 未支持的返回只记录协议失败。
            report = FailureReport(FailureKind.PROTOCOL_ERROR)
        # 离开 except 后才结算,迟到结算的受控错误不串联原执行者异常。
        return self._attempts.fail(claim, report, origin=origin)

    def register_feed_value(
        self,
        raw_request: object,
        *,
        policy_version: str = "v1",
        feed_gate: FeedGate | None = None,
    ) -> RequestReceipt:
        """生产登记:派生来源、冻结预算及依据在同一写事务提交。"""
        return self._register(
            raw_request, policy_version=policy_version, feed_gate=feed_gate
        )

    def language_basis(self, receipt_id: str) -> dict[str, Any]:
        from paper_radar.screening_tasks.language import load

        receipt = self.get_receipt(receipt_id)
        with (
            task_database(self.database, write=False) as engine,
            task_transaction(engine, write=False) as connection,
        ):
            return load(connection, receipt.budget_id)

    def language_status(
        self, paper_id: str, *, policy_version: str = "v1"
    ) -> dict[str, Any]:
        from paper_radar.screening_tasks.language import derive, retain

        with task_database(self.database, write=True) as engine:
            require_current_revision(engine)
            with task_transaction(engine, write=True) as connection:
                basis = derive(connection, paper_id, policy_version)
                retain(connection, basis)
                return basis

    def language_observations(self, paper_id: str) -> tuple[dict[str, Any], ...]:
        from paper_radar.screening_tasks.language import observations

        with (
            task_database(self.database, write=False) as engine,
            task_transaction(engine, write=False) as connection,
        ):
            require_current_revision(engine)
            return observations(connection, paper_id)

    def register_language_policy(self, version: str) -> None:
        """登记新策略身份,沿用已裁决的 v1 映射;不允许修改旧身份。"""
        from paper_radar.screening_tasks.language import POLICIES, encode, policies

        if (
            type(version) is not str
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", version) is None
        ):
            raise TaskError(TaskReason.INVALID_REQUEST)
        with task_database(self.database, write=True) as engine:
            require_current_revision(engine)
            with task_transaction(engine, write=True) as connection:
                old = connection.execute(
                    select(policies.c.mapping_json).where(
                        policies.c.policy_version == version
                    )
                ).scalar_one_or_none()
                content = encode(POLICIES["v1"])
                if old is not None and old != content:
                    raise TaskError(TaskReason.CORRUPT_REFERENCE)
                if old is None:
                    connection.execute(
                        policies.insert().values(
                            policy_version=version, mapping_json=content
                        )
                    )

    def bind_feed_journal(self, feed_id: str, journal: str) -> None:
        """显式登记已存在 Feed 的期刊归属;不创建或订阅 Feed。"""
        from paper_radar.papers.tables import feeds
        from paper_radar.screening_tasks.language import ENDPOINTS, POLICIES, bindings

        if journal not in POLICIES["v1"]:
            raise TaskError(TaskReason.INVALID_REQUEST)
        with task_database(self.database, write=True) as engine:
            require_current_revision(engine)
            with task_transaction(engine, write=True) as connection:
                if (
                    connection.execute(
                        select(feeds.c.feed_id).where(feeds.c.feed_id == feed_id)
                    ).first()
                    is None
                ):
                    raise TaskError(TaskReason.INVALID_REQUEST)
                endpoint = connection.execute(
                    select(feeds.c.url).where(feeds.c.feed_id == feed_id)
                ).scalar_one()
                if endpoint in ENDPOINTS and ENDPOINTS[endpoint] != journal:
                    raise TaskError(TaskReason.CONTEXT_CONFLICT)
                old = connection.execute(
                    select(bindings.c.journal).where(bindings.c.feed_id == feed_id)
                ).scalar_one_or_none()
                if old is not None and old != journal:
                    raise TaskError(TaskReason.CONTEXT_CONFLICT)
                if old is None:
                    connection.execute(
                        bindings.insert().values(feed_id=feed_id, journal=journal)
                    )

    def register(self, raw_request: object) -> RequestReceipt:
        return self._register(raw_request)

    def _register(
        self,
        raw_request: object,
        *,
        policy_version: str | None = None,
        feed_gate: FeedGate | None = None,
    ) -> RequestReceipt:
        from paper_radar.screening_tasks.language import (
            derive,
            frozen,
            required,
            retain,
        )

        if policy_version is not None:
            if (
                type(raw_request) is not dict
                or raw_request.get("stage") != "value"
                or "original_title_is_zh" in raw_request
            ):
                raise TaskError(TaskReason.INVALID_REQUEST)
            # 仅供严格请求解析;提交事务内替换为已冻结或派生的值。
            raw_request = {**raw_request, "original_title_is_zh": False}
        request = parse_request(raw_request)
        with task_database(self.database, write=True) as engine:
            try:
                require_current_revision(engine)
                # 精确 manual 重放先于当前映射,保留原回执即使论文已变化或缺项。
                with task_transaction(engine, write=False, begin=False) as connection:
                    if policy_version is not None and request.request_id is not None:
                        old_language = connection.execute(
                            select(budgets.c.original_title_is_zh)
                            .select_from(requests.join(tasks).join(budgets))
                            .where(requests.c.request_id == request.request_id)
                        ).first()
                        if old_language is not None:
                            request = request.model_copy(
                                update={"original_title_is_zh": old_language[0]}
                            )
                    replayed = replay_request(connection, request)
                    if replayed is not None:
                        if feed_gate is not None:
                            previous_gate = find_feed_gate(
                                connection, feed_gate.request_key
                            )
                            if (
                                previous_gate is None
                                or previous_gate["receipt_id"] != replayed.receipt_id
                            ):
                                raise TaskError(TaskReason.REQUEST_CONFLICT)
                        return replayed
                mapping = PaperFacts(self.database).map_screening_inputs(
                    paper_id=request.paper_id, snapshot_id=request.snapshot_id
                )
                stage_input, evidence = require_stage_mapping(mapping, request.stage)
                snapshot = load_config_snapshot(self.database, request.snapshot_id)
                if isinstance(request, ValueRequest):
                    try:
                        stage_input.value_prediction_context(
                            snapshot, original_title_is_zh=request.original_title_is_zh
                        )
                    except StageInputError as error:
                        assert isinstance(error.reason, BuildReason)
                        raise TaskError(
                            TaskReason.INVALID_CONTEXT,
                            build_reason=error.reason,
                            field=error.field,
                        ) from None
                with task_transaction(engine, write=True) as connection:
                    # 并发另一登记可能已经完成相同 manual 请求,应重放其原回执。
                    if policy_version is not None:
                        assert isinstance(request, ValueRequest)
                        existing_budget = (
                            connection.execute(
                                select(budgets).where(
                                    budgets.c.paper_id == request.paper_id,
                                    budgets.c.stage == "value",
                                    budgets.c.fingerprint == stage_input.fingerprint,
                                )
                            )
                            .mappings()
                            .first()
                        )
                        basis = None
                        if existing_budget is not None:
                            language = existing_budget["original_title_is_zh"]
                        else:
                            basis = derive(connection, request.paper_id, policy_version)
                            if basis["status"] != "resolved":
                                retain(connection, basis)
                                connection.commit()
                                raise TaskError(
                                    TaskReason.LANGUAGE_AMBIGUOUS
                                    if basis["status"] == "ambiguous"
                                    else TaskReason.LANGUAGE_MISSING
                                )
                            language = basis["original_title_is_zh"]
                        request = request.model_copy(
                            update={"original_title_is_zh": language}
                        )
                    replayed = replay_request(connection, request)
                    if replayed is not None:
                        if feed_gate is not None:
                            previous_gate = find_feed_gate(
                                connection, feed_gate.request_key
                            )
                            if (
                                previous_gate is None
                                or previous_gate["receipt_id"] != replayed.receipt_id
                            ):
                                raise TaskError(TaskReason.REQUEST_CONFLICT)
                        return replayed
                    if feed_gate is not None and (
                        evidence.version_id != feed_gate.version_id
                        or evidence.revision_no != feed_gate.revision_no
                        or mapping.boundary.value is None
                        or mapping.boundary.value.fingerprint
                        != feed_gate.boundary_fingerprint
                    ):
                        raise TaskError(TaskReason.FACTS_CHANGED)
                    current = resolve_revision(connection, paper_id=request.paper_id)
                    if evidence_values(current) != evidence_values(evidence):
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
                        connection, request, stage_input, evidence
                    )
                    if policy_version is not None and basis is not None:
                        identifier = retain(connection, basis)
                        connection.execute(
                            frozen.insert().values(
                                budget_id=result.budget_id, resolution_id=identifier
                            )
                        )
                        connection.execute(
                            required.insert().values(budget_id=result.budget_id)
                        )
                    if feed_gate is not None:
                        retain_feed_gate(connection, feed_gate, result.receipt_id)
                    return result
            except SQLAlchemyError as error:
                raise database_error(error) from None

    def get_receipt(self, receipt_id: str) -> RequestReceipt:
        if (
            type(receipt_id) is not str
            or re.fullmatch(r"[0-9a-f]{64}", receipt_id) is None
        ):
            raise TaskError(TaskReason.REQUEST_NOT_FOUND)
        with task_database(self.database, write=False) as engine:
            try:
                require_current_revision(engine)
                with task_transaction(engine, write=False) as connection:
                    row = receipt_row(connection, receipt_id)
                    if row is None:
                        raise TaskError(TaskReason.REQUEST_NOT_FOUND)
                    return to_receipt(row)
            except SQLAlchemyError as error:
                raise database_error(error) from None

    def receipts(self, paper_id: str) -> tuple[RequestReceipt, ...]:
        with task_database(self.database, write=False) as engine:
            try:
                require_current_revision(engine)
                with task_transaction(engine, write=False) as connection:
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

    def load_input(self, receipt_id: str) -> FrozenInput:
        receipt = self.get_receipt(receipt_id)
        with task_database(self.database, write=False) as engine:
            try:
                require_current_revision(engine)
                with task_transaction(engine, write=False) as connection:
                    budget = (
                        connection.execute(
                            select(budgets).where(
                                budgets.c.budget_id == receipt.budget_id
                            )
                        )
                        .mappings()
                        .one()
                    )
                    return load_frozen(self.database, connection, dict(budget))
            except (StageInputError, ConfigError, ValueError, TypeError, KeyError):
                raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
            except SQLAlchemyError as error:
                raise database_error(error) from None

    def validate_all(self) -> None:
        from paper_radar.screening_tasks.attempt_integrity import validate_attempts
        from paper_radar.screening_tasks.integrity import validate_registration

        with task_database(self.database, write=False) as engine:
            try:
                require_current_revision(engine)
                with task_transaction(engine, write=False) as connection:
                    from paper_radar.screening_tasks.language import validate

                    validate(connection)
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
