"""完整候选的权威接收与唯一分析原子提交;持久序号是唯一末次依据。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paper_radar.read_tasks.service import ReadTasks

from uuid import uuid4

from sqlalchemy import insert, select

from paper_radar.read_tasks import tables as t
from paper_radar.read_tasks.models import (
    ReadAnalysis,
    ReadHandle,
    ReadTask,
    ReadTaskError,
)
from paper_radar.read_tasks.queries import budget_for
from paper_radar.read_tasks.repository import canonical, records, sha, transaction
from paper_radar.reading.acceptance_v2 import ReadV2OutputError, validate_read_output_v2
from paper_radar.reading.schema import (
    ReadAnalysisOutput,
    ReusablePoint,
    SupportedStatement,
)


def referenced_ids(output: ReadAnalysisOutput) -> tuple[str, ...]:
    items: list[SupportedStatement | ReusablePoint] = [
        *output.main_findings,
        *output.reusable_points,
        *output.key_limitations,
        output.research_value_reason,
        output.reuse_feasibility_reason,
    ]
    return tuple(sorted({ref.evidence_id for item in items for ref in item.evidence}))


def submit(
    service: ReadTasks,
    handle: ReadHandle,
    raw: bytes,
    *,
    executor_kind: str = "test",
    audit_json: str = "{}",
) -> ReadAnalysis | ReadTask:
    if type(raw) is not bytes:
        raise ReadTaskError("invalid_request")
    # 先核验所有权;历史精确提交不依赖租约仍有效,也不重跑模型。
    with transaction(service.database) as connection:
        _, outcome = service._owned(connection, handle, settled=True)
        previous = (
            connection.execute(
                select(t.analyses).where(t.analyses.c.attempt_id == handle.attempt_id)
            )
            .mappings()
            .first()
        )
        if previous is not None:
            if (
                previous["candidate_sha256"],
                previous["executor_kind"],
                previous["audit_json"],
            ) != (sha(raw), executor_kind, audit_json):
                raise ReadTaskError("settlement_conflict")
            return service.analysis(previous["analysis_id"])
        if outcome is not None:
            raise ReadTaskError("settlement_conflict")
    prepared = service.prepare(handle.task_id)
    # 外部handle ordinal不可成为接收事实,使用持久attempt行。
    with transaction(service.database) as connection:
        attempt, _ = service._owned(connection, handle)
        ordinal = attempt["ordinal"]
    try:
        result = validate_read_output_v2(raw, prepared.context, attempt_ordinal=ordinal)
    except ReadV2OutputError as error:
        with transaction(service.database, write=True) as connection:
            service._owned(connection, handle)
            connection.execute(
                insert(t.outcomes).values(
                    attempt_id=handle.attempt_id,
                    failure="output_invalid",
                    issues_json=canonical(
                        [
                            {"location": v.location, "category": v.category.value}
                            for v in error.issues
                        ]
                    ),
                    settled_at=service._now().isoformat(),
                )
            )
        service.log.emit(
            "failed",
            component="read",
            stage="read",
            task_id=handle.task_id,
            attempt=ordinal,
            kind="output_invalid",
        )
        return service.task(handle.task_id)
    # 制品先完整发布;失败可留下未引用制品,但数据库不出现半条分析。
    candidate = service.artifacts.store.publish_single("model_success_response", (raw,))
    analysis_id = str(uuid4())
    with transaction(service.database, write=True) as connection:
        _, settled = service._owned(connection, handle, settled=True)
        if settled is not None:
            prior = (
                connection.execute(
                    select(t.analyses).where(
                        t.analyses.c.attempt_id == handle.attempt_id
                    )
                )
                .mappings()
                .first()
            )
            if prior is not None and (
                prior["candidate_sha256"],
                prior["executor_kind"],
                prior["audit_json"],
            ) == (sha(raw), executor_kind, audit_json):
                return service.analysis(prior["analysis_id"])
            raise ReadTaskError("settlement_conflict")
        budget = budget_for(connection, handle.task_id)
        if connection.execute(
            select(t.analyses.c.analysis_id).where(
                t.analyses.c.task_id == handle.task_id
            )
        ).first():
            raise ReadTaskError("settlement_conflict")
        now = service._now().isoformat()
        connection.execute(
            insert(t.outcomes).values(
                attempt_id=handle.attempt_id,
                failure=None,
                issues_json="[]",
                settled_at=now,
            )
        )
        connection.execute(
            insert(t.analyses).values(
                analysis_id=analysis_id,
                task_id=handle.task_id,
                attempt_id=handle.attempt_id,
                candidate_artifact_id=candidate.artifact_id,
                candidate_sha256=sha(raw),
                output_json=result.analysis.model_dump_json(),
                degrade_policy=result.degrade_policy,
                attempt_ordinal=ordinal,
                evidence_rule_version=result.evidence_rule_version,
                numeric_rule_version=result.numeric_rule_version,
                limitation_rule_version=result.content_limitation_rule_version,
                discards_json=records(result.discards),
                diagnostics_json=records(result.diagnostics),
                warnings_json=records(result.warnings),
                executor_kind=executor_kind,
                audit_json=audit_json,
                settled_at=now,
            )
        )
        for evidence_id in referenced_ids(result.analysis):
            connection.execute(
                insert(t.evidence).values(
                    analysis_id=analysis_id,
                    evidence_id=evidence_id,
                    artifact_id=budget["artifact_id"],
                )
            )
    service.log.emit(
        "succeeded",
        component="read",
        stage="read",
        task_id=handle.task_id,
        attempt=ordinal,
    )
    return service.analysis(analysis_id)
