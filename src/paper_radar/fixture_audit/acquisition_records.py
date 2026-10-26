"""从同一只读事务重建计划和取得历史,不从 blob 存在推断成功。"""

from __future__ import annotations

import hashlib
import re

from pydantic import ValidationError
from sqlalchemy import Connection, select

from paper_radar.fixture_audit.acquisition_models import (
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
from paper_radar.fixture_audit.history_rules import require_historical_plan
from paper_radar.fixture_audit.resume_rules import can_continue


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
                or row["plan_json"] != plan.model_dump_json()
            ):
                raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit.plan")
            require_historical_plan(plan)
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
        previous_records: dict[str, RouteExecution] = {}
        continued: set[str] = set()
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
            previous_id = row["previous_execution_id"]
            sample = re.fullmatch(
                r"sample-(?:aies|jgr|qjrms|dqkx)-(?:feed|[0-9]+)-(?:feed|doi_ra|registry_crossref|registry_datacite|publisher)-([0-9]+)",
                key,
            )
            matrix = re.fullmatch(
                r"(matrix-[0-9a-f]{32}-[a-z_]+-[a-z_]+)-resume-([0-9]+)", key
            )
            if sample:
                ordinal = int(sample[1])
                predecessor = previous_records.get(previous_id or "")
                if (
                    ordinal < 1
                    or (ordinal == 1 and previous_id is not None)
                    or (
                        ordinal > 1
                        and (
                            predecessor is None
                            or predecessor.request_key
                            != key.rsplit("-", 1)[0] + f"-{ordinal - 1}"
                            or (
                                request.route != "feed"
                                and not can_continue(predecessor)
                            )
                        )
                    )
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.continuation"
                    )
            if matrix:
                ordinal = int(matrix[2])
                predecessor = previous_records.get(previous_id or "")
                if (
                    ordinal < 1
                    or predecessor is None
                    or not can_continue(predecessor)
                    or (
                        ordinal > 1
                        and predecessor.request_key
                        != f"{matrix[1]}-resume-{ordinal - 1}"
                    )
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.continuation"
                    )
            if previous_id is not None:
                previous = previous_records.get(previous_id)
                if (
                    previous is None
                    or previous.plan_id != plan_id
                    or previous.request != request
                    or previous.settlement is None
                    or previous.reason == "channel_not_installed"
                    or previous_id in continued
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="audit.continuation"
                    )
                continued.add(previous_id)
            seen.add(execution_id)
            executions[plan_id].append(
                RouteExecution(
                    execution_id=execution_id,
                    plan_id=plan_id,
                    request_key=key,
                    request=request,
                    started_at=row["started_at"],
                    previous_execution_id=previous_id,
                    settlement=settlements.get(execution_id),
                )
            )
            previous_records[execution_id] = executions[plan_id][-1]
        if not settlements.keys() <= seen:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit.settlement")
        return tuple(
            AuditView(plan=plan, executions=tuple(executions[plan.plan_id]))
            for plan in plans.values()
        )
    except (ValidationError, TypeError, ValueError):
        raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit") from None
