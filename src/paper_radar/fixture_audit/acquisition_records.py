"""从同一只读事务重建计划和取得历史,不从 blob 存在推断成功。"""

from __future__ import annotations

import hashlib

from pydantic import ValidationError
from sqlalchemy import Connection, select

from paper_radar.fixture_audit.acquisition_models import (
    ACQUISITION_STRATEGY_VERSION,
    CATEGORY_RULES_VERSION,
    CHANNELS_VERSION,
    HTTP_RULES_VERSION,
    PARSER_VERSION,
    SAMPLING_RULES_VERSION,
    UA_TEMPLATE_VERSION,
    AuditPlan,
    AuditView,
    RouteExecution,
    SourceRequest,
    SourceSettlement,
    identity_sha256,
)
from paper_radar.fixture_audit.acquisition_policy import (
    FEED_ENDPOINTS,
    checked_source_url,
    normalize_request,
)
from paper_radar.fixture_audit.acquisition_tables import (
    audit_plans,
    audit_route_settlements,
    audit_route_starts,
)
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason


def execution_identity(plan_id: str, request_key: str, request: SourceRequest) -> str:
    return hashlib.sha256(
        f"{plan_id}\0{request_key}\0{identity_sha256(request)}".encode()
    ).hexdigest()


def load_audits(connection: Connection) -> tuple[AuditView, ...]:
    try:
        plans: dict[str, AuditPlan] = {}
        for row in connection.execute(select(audit_plans)).mappings():
            plan = AuditPlan.model_validate_json(row["plan_json"])
            if (
                plan.plan_id != row["plan_id"]
                or plan.plan_key != row["plan_key"]
                or identity_sha256(plan.model_copy(update={"plan_id": ""}))
                != plan.plan_id
                or plan.endpoints != FEED_ENDPOINTS
                or plan.sampling_rules_version != SAMPLING_RULES_VERSION
                or plan.category_rules_version != CATEGORY_RULES_VERSION
                or (
                    plan.acquisition_strategy_version,
                    plan.channels_version,
                    plan.http_rules_version,
                    plan.parser_version,
                    plan.ua_template_version,
                )
                != (
                    ACQUISITION_STRATEGY_VERSION,
                    CHANNELS_VERSION,
                    HTTP_RULES_VERSION,
                    PARSER_VERSION,
                    UA_TEMPLATE_VERSION,
                )
                or row["plan_json"] != plan.model_dump_json()
            ):
                raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit.plan")
            plans[plan.plan_id] = plan
        settlements: dict[str, SourceSettlement] = {}
        for row in connection.execute(select(audit_route_settlements)).mappings():
            value = SourceSettlement.model_validate_json(row["settlement_json"])
            if (
                value.artifact_id != row["artifact_id"]
                or value.model_dump_json() != row["settlement_json"]
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="audit.settlement"
                )
            settlements[row["execution_id"]] = value
        executions: dict[str, list[RouteExecution]] = {key: [] for key in plans}
        seen: set[str] = set()
        for row in connection.execute(
            select(audit_route_starts).order_by(audit_route_starts.c.event_no)
        ).mappings():
            request = SourceRequest.model_validate_json(row["request_json"])
            plan_id, key, execution_id = (
                row["plan_id"],
                row["request_key"],
                row["execution_id"],
            )
            if (
                plan_id not in plans
                or normalize_request(request) != request
                or execution_identity(plan_id, key, request) != execution_id
                or request.acquisition_strategy_version
                != plans[plan_id].acquisition_strategy_version
                or request.model_dump_json() != row["request_json"]
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="audit.request"
                )
            settlement = settlements.get(execution_id)
            if settlement and settlement.http:
                for fact in settlement.http.requests:
                    if checked_source_url(fact.url, request) is not None:
                        raise FixtureError(
                            FixtureReason.CORRUPT_REFERENCE, path="audit.http_url"
                        )
            seen.add(execution_id)
            executions[plan_id].append(
                RouteExecution(
                    execution_id=execution_id,
                    plan_id=plan_id,
                    request_key=key,
                    request=request,
                    started_at=row["started_at"],
                    settlement=settlements.get(execution_id),
                )
            )
        if not settlements.keys() <= seen:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit.settlement")
        return tuple(
            AuditView(plan=plan, executions=tuple(executions[plan.plan_id]))
            for plan in plans.values()
        )
    except (ValidationError, TypeError, ValueError):
        raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit") from None
