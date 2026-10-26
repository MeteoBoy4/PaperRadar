"""公共 fixture 服务的审计持久化部分;网络始终位于短事务外。"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.fixture_audit.acquisition_identity import capture_code_identity
from paper_radar.fixture_audit.acquisition_models import (
    AuditPlan,
    AuditView,
    Channel,
    CodeIdentity,
    HTTPFacts,
    RouteExecution,
    SourceRequest,
    SourceSettlement,
    identity_sha256,
    revalidate_model,
)
from paper_radar.fixture_audit.acquisition_policy import (
    FEED_ENDPOINTS,
    normalize_request,
    validate_contact,
)
from paper_radar.fixture_audit.acquisition_records import (
    execution_identity,
    load_audits,
)
from paper_radar.fixture_audit.acquisition_tables import (
    audit_plans,
    audit_route_settlements,
    audit_route_starts,
)
from paper_radar.fixture_audit.audit_protection import AuditProtection
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.source_http import (
    SourceExecutor,
    SourceHTTPExecutor,
    SourceResponse,
    body_is_contact_free,
)
from paper_radar.fixture_audit.source_validation import inspect_source
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class AcquisitionService:
    def __init__(
        self,
        database: Path,
        data_root: Path | None,
        source_executors: Mapping[Channel, SourceExecutor] | None = None,
    ) -> None:
        self.database, self.data_root = database, data_root
        self.executors: dict[Channel, SourceExecutor] = (
            dict(source_executors)
            if source_executors is not None
            else {"http": SourceHTTPExecutor()}
        )

    def list_audits(self) -> tuple[AuditView, ...]:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                return load_audits(connection)
        except SQLAlchemyError:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit") from None
        finally:
            engine.dispose()

    def show_audit(self, plan_id: str) -> AuditView:
        for view in self.list_audits():
            if view.plan.plan_id == plan_id:
                return view
        raise FixtureError(FixtureReason.RECORD_NOT_FOUND, path="plan_id")

    def create_audit_plan(
        self,
        *,
        contact_email: str | None,
        target_count: int = 5,
        plan_key: str | None = None,
        code_identity: CodeIdentity | None = None,
    ) -> AuditPlan:
        validate_contact(contact_email)
        try:
            if code_identity is not None:
                code_identity = revalidate_model(code_identity, CodeIdentity)
            plan = AuditPlan(
                plan_id="",
                plan_key=plan_key if plan_key is not None else uuid4().hex,
                target_count=target_count,
                endpoints=FEED_ENDPOINTS,
                code_identity=code_identity or capture_code_identity(),
                created_at=utc_now(),
            )
        except (ValidationError, ValueError, TypeError, RecursionError):
            raise FixtureError(FixtureReason.INVALID_PLAN, path="plan") from None
        plan = plan.model_copy(update={"plan_id": identity_sha256(plan)})
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                for view in load_audits(connection):
                    if view.plan.plan_key == plan.plan_key:
                        if view.plan.model_copy(
                            update={"plan_id": "", "created_at": ""}
                        ) != plan.model_copy(update={"plan_id": "", "created_at": ""}):
                            raise FixtureError(
                                FixtureReason.PLAN_CONFLICT, path="plan_key"
                            )
                        return view.plan
                connection.execute(
                    audit_plans.insert().values(
                        plan_id=plan.plan_id,
                        plan_key=plan.plan_key,
                        plan_json=plan.model_dump_json(),
                    )
                )
                connection.commit()
                return plan
        except SQLAlchemyError:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit") from None
        finally:
            engine.dispose()

    def _acquire_source(
        self,
        plan_id: str,
        *,
        request_key: str,
        request: SourceRequest,
        contact_email: str | None,
        previous_execution_id: str | None = None,
    ) -> RouteExecution:
        contact = validate_contact(contact_email)
        try:
            request = revalidate_model(request, SourceRequest)
        except (ValueError, TypeError, RecursionError):
            raise FixtureError(
                FixtureReason.INVALID_REQUEST, path="source_request"
            ) from None
        if (
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", request_key) is None
            or contact.casefold() in request.model_dump_json().casefold()
        ):
            raise FixtureError(FixtureReason.INVALID_REQUEST, path="request_key")
        request = normalize_request(request)
        self._validate_prior(request)
        view = self.show_audit(plan_id)
        if (
            request.acquisition_strategy_version
            != view.plan.acquisition_strategy_version
        ):
            raise FixtureError(
                FixtureReason.REQUEST_CONFLICT, path="acquisition_strategy_version"
            )
        execution_id = execution_identity(plan_id, request_key, request)
        for value in view.executions:
            if value.request_key == request_key:
                if (
                    value.request != request
                    or value.previous_execution_id != previous_execution_id
                ):
                    raise FixtureError(
                        FixtureReason.REQUEST_CONFLICT, path="request_key"
                    )
                if value.settlement is None:
                    raise FixtureError(FixtureReason.EXECUTION_INCOMPLETE)
                return value
        if previous_execution_id is not None:
            previous = next(
                (
                    item
                    for item in view.executions
                    if item.execution_id == previous_execution_id
                ),
                None,
            )
            if (
                previous is None
                or previous.request != request
                or previous.settlement is None
                or previous.reason == "channel_not_installed"
                or any(
                    item.previous_execution_id == previous_execution_id
                    for item in view.executions
                )
            ):
                raise FixtureError(
                    FixtureReason.INVALID_REFERENCE, path="audit.continuation"
                )
        value = RouteExecution(
            execution_id=execution_id,
            plan_id=plan_id,
            request_key=request_key,
            request=request,
            started_at=utc_now(),
            previous_execution_id=previous_execution_id,
        )
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    audit_route_starts.insert().values(
                        execution_id=execution_id,
                        plan_id=plan_id,
                        request_key=request_key,
                        request_json=request.model_dump_json(),
                        started_at=value.started_at,
                        previous_execution_id=previous_execution_id,
                    )
                )
                connection.commit()
            executor = self.executors.get(request.channel)
            if executor is None:
                settlement = SourceSettlement(
                    reason="channel_not_installed", settled_at=utc_now()
                )
            else:
                try:
                    response = executor.fetch(request, contact_email=contact)
                    facts = revalidate_model(response.facts, HTTPFacts)
                    if response.body is not None and (
                        type(response.body) is not bytes
                        or len(response.body) > 8 * 1024 * 1024
                    ):
                        raise ValueError("executor_body")
                    response = SourceResponse(facts, response.body)
                except Exception:
                    # A broken injected executor cannot reveal arbitrary exception
                    # text or claim a known request count after losing its result.
                    raise FixtureError(
                        FixtureReason.EXECUTION_INCOMPLETE, path="executor"
                    ) from None
                if (
                    contact.casefold() in response.facts.model_dump_json().casefold()
                    or (
                        response.body is not None
                        and not body_is_contact_free(
                            response.body, response.facts.decoding, contact
                        )
                    )
                ):
                    raise FixtureError(FixtureReason.INVALID_REQUEST, path="executor")
                settlement = self._response_settlement(request, response)

            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    audit_route_settlements.insert().values(
                        execution_id=execution_id,
                        settlement_json=settlement.model_dump_json(),
                        artifact_id=settlement.artifact_id,
                    )
                )
                connection.commit()
            return value.model_copy(update={"settlement": settlement})
        except SQLAlchemyError:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit") from None
        finally:
            engine.dispose()

    def audit_execution(self, plan_id: str) -> AuditProtection:
        self.show_audit(plan_id)
        return AuditProtection(self.database, self.data_root, plan_id)

    def acquire_source(
        self,
        plan_id: str,
        *,
        request_key: str,
        request: SourceRequest,
        contact_email: str | None,
        protection: AuditProtection | None = None,
        previous_execution_id: str | None = None,
    ) -> RouteExecution:
        validate_contact(contact_email)
        if protection is not None:
            if (
                protection.fd is None
                or protection.plan_id != plan_id
                or protection.database.resolve() != self.database.resolve()
            ):
                raise FixtureError(FixtureReason.EXECUTION_BUSY, path="plan_id")
            return self._acquire_source(
                plan_id,
                request_key=request_key,
                request=request,
                contact_email=contact_email,
                previous_execution_id=previous_execution_id,
            )
        with self.audit_execution(plan_id):
            return self._acquire_source(
                plan_id,
                request_key=request_key,
                request=request,
                contact_email=contact_email,
                previous_execution_id=previous_execution_id,
            )

    def _response_settlement(
        self, request: SourceRequest, response: SourceResponse
    ) -> SourceSettlement:
        facts = response.facts
        if facts.status_code == 304 and facts.reason == "acquired":
            prior_id = request.conditional_headers.prior_artifact_id
            if prior_id is None or self.data_root is None:
                return SourceSettlement(
                    reason="invalid_response", http=facts, settled_at=utc_now()
                )
            store = ArtifactStore(self.database, self.data_root)
            body = store.read_artifact(prior_id)["payload"]
            prior = self._validate_prior(request)
            if prior is None or prior.content_decoding is None:
                raise FixtureError(
                    FixtureReason.INVALID_REFERENCE, path="prior_artifact_id"
                )
            inspected = inspect_source(request, body, prior.content_decoding)
            if not inspected.retain:
                raise FixtureError(
                    FixtureReason.INVALID_REFERENCE, path="prior_artifact_id"
                )
            return SourceSettlement(
                reason=inspected.reason,
                http=facts,
                artifact_id=prior_id,
                payload_sha256=hashlib.sha256(body).hexdigest(),
                size_bytes=len(body),
                identity_doi=inspected.identity_doi,
                reused_prior=True,
                content_decoding=prior.content_decoding,
                settled_at=utc_now(),
            )
        if facts.reason != "acquired" or response.body is None:
            reason = (
                facts.reason
                if response.body is not None or facts.reason != "acquired"
                else "invalid_response"
            )
            if request.route == "doi_ra" and reason not in {
                "not_attempted",
                "channel_not_installed",
            }:
                reason = "agency_unknown"
            return SourceSettlement(reason=reason, http=facts, settled_at=utc_now())
        inspected = inspect_source(request, response.body, facts.decoding or "utf-8")
        artifact_id, sha256, size_bytes = None, None, None
        if inspected.retain:
            if self.data_root is None:
                raise FixtureError(FixtureReason.INVALID_REQUEST, path="data_root")
            artifact = ArtifactStore(self.database, self.data_root).publish_single(
                "source_snapshot", (response.body,)
            )
            artifact_id = artifact.artifact_id
            sha256, size_bytes = (
                hashlib.sha256(response.body).hexdigest(),
                len(response.body),
            )
        return SourceSettlement(
            reason=inspected.reason,
            http=facts,
            artifact_id=artifact_id,
            payload_sha256=sha256,
            size_bytes=size_bytes,
            identity_doi=inspected.identity_doi,
            agency=inspected.agency,
            content_decoding=(facts.decoding or "utf-8") if inspected.retain else None,
            settled_at=utc_now(),
        )

    def validate_all(self) -> None:
        for view in self.list_audits():
            for execution in view.executions:
                settlement = execution.settlement
                prior = self._validate_prior(execution.request)
                if settlement is None:
                    continue
                if settlement.reused_prior != (
                    settlement.http is not None and settlement.http.status_code == 304
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.conditional"
                    )
                if settlement.reused_prior and (
                    prior is None
                    or settlement.artifact_id != prior.artifact_id
                    or settlement.content_decoding != prior.content_decoding
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.conditional"
                    )
                if (
                    settlement.reason == "channel_not_installed"
                    and settlement.http is not None
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.channel"
                    )
                if (
                    settlement.agency is not None
                    and execution.request.route != "doi_ra"
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.agency"
                    )
                if (
                    execution.request.route == "doi_ra"
                    and settlement.reason in {"acquired", "agency_unsupported"}
                    and (
                        settlement.agency is None
                        or (settlement.reason == "acquired")
                        != (settlement.agency in {"Crossref", "DataCite"})
                    )
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.agency"
                    )
                if settlement.artifact_id is None:
                    if (
                        settlement.payload_sha256 is not None
                        or settlement.size_bytes is not None
                        or settlement.content_decoding is not None
                        or (
                            settlement.reason == "acquired"
                            and execution.request.route != "doi_ra"
                        )
                    ):
                        raise FixtureError(
                            FixtureReason.CORRUPT_REFERENCE, path="audit.artifact"
                        )
                    continue
                if (
                    self.data_root is None
                    or settlement.http is None
                    or settlement.http.status_code not in (200, 304)
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.artifact"
                    )
                store = ArtifactStore(self.database, self.data_root)
                artifact = store.get_artifact(settlement.artifact_id)
                body = store.read_artifact(settlement.artifact_id)["payload"]
                inspected = inspect_source(
                    execution.request,
                    body,
                    settlement.content_decoding or "utf-8",
                )
                if (
                    settlement.content_decoding is None
                    or (
                        not settlement.reused_prior
                        and settlement.content_decoding
                        != (settlement.http.decoding or "utf-8")
                    )
                    or artifact.kind != "source_snapshot"
                    or not inspected.retain
                    or inspected.reason != settlement.reason
                    or inspected.identity_doi != settlement.identity_doi
                    or inspected.agency != settlement.agency
                    or hashlib.sha256(body).hexdigest() != settlement.payload_sha256
                    or len(body) != settlement.size_bytes
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.artifact"
                    )

    def _validate_prior(self, request: SourceRequest) -> SourceSettlement | None:
        conditions = request.conditional_headers
        if (
            conditions.if_none_match is None
            and conditions.if_modified_since is None
            and conditions.prior_artifact_id is None
        ):
            return None
        if conditions.prior_artifact_id is not None:
            for view in self.list_audits():
                for execution in view.executions:
                    settlement = execution.settlement
                    if (
                        settlement
                        and settlement.artifact_id == conditions.prior_artifact_id
                        and not settlement.reused_prior
                        and execution.request.model_copy(
                            update={"conditional_headers": None}
                        )
                        == request.model_copy(update={"conditional_headers": None})
                    ):
                        return settlement
        raise FixtureError(
            FixtureReason.INVALID_REFERENCE,
            path="conditional_headers.prior_artifact_id",
        )

    def close_unknown_source(
        self, execution_id: str, *, protection: AuditProtection
    ) -> RouteExecution:
        """显式选样继续所需的窄结算,不假定已发送请求数。"""
        if (
            protection.fd is None
            or protection.database.resolve() != self.database.resolve()
        ):
            raise FixtureError(FixtureReason.EXECUTION_BUSY, path="plan_id")
        view = self.show_audit(protection.plan_id)
        previous = next(
            (item for item in view.executions if item.execution_id == execution_id),
            None,
        )
        if previous is None:
            raise FixtureError(FixtureReason.INVALID_REFERENCE, path="execution_id")
        if previous.settlement is not None:
            if previous.reason != "outcome_unknown":
                raise FixtureError(FixtureReason.RESULT_CONFLICT, path="execution_id")
            return previous
        settlement = SourceSettlement(reason="outcome_unknown", settled_at=utc_now())
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    audit_route_settlements.insert().values(
                        execution_id=execution_id,
                        settlement_json=settlement.model_dump_json(),
                        artifact_id=None,
                    )
                )
                connection.commit()
            return previous.model_copy(update={"settlement": settlement})
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.RESULT_CONFLICT, path="execution_id"
            ) from None
        finally:
            engine.dispose()
