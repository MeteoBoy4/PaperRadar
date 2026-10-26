"""完整审计汇总的不可变事实边界;只冻结引用,不复制审计内容。"""

from __future__ import annotations

import hashlib

from pydantic import ValidationError
from sqlalchemy import Column, Connection, ForeignKey, String, Table, Text, select

from paper_radar.fixture_audit.abstract_models import AbstractAuditView
from paper_radar.fixture_audit.abstract_rules import project
from paper_radar.fixture_audit.acquisition_models import identity_sha256
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.models import FrozenModel, Journal
from paper_radar.fixture_audit.sampling_models import SamplingAuditView
from paper_radar.storage.schema import metadata

summaries = Table(
    "audit_summaries",
    metadata,
    Column("summary_sha256", String(64), primary_key=True),
    Column("plan_id", String(64), ForeignKey("audit_plans.plan_id"), nullable=False),
    Column("content_json", Text, nullable=False),
)


class SummaryBoundary(FrozenModel):
    plan_id: str
    summary_sha256: str
    # None records a started execution whose settlement was not yet visible.
    executions: tuple[tuple[str, str | None], ...]
    matrix_rows: tuple[str, ...]
    feeds: dict[Journal, str]
    sampling_events: dict[Journal, tuple[str, ...]]


def summary_sha256(view: AbstractAuditView) -> str:
    return hashlib.sha256(view.model_dump_json().encode()).hexdigest()


def boundary_for(view: AbstractAuditView) -> SummaryBoundary:
    return SummaryBoundary(
        plan_id=view.plan.plan_id,
        summary_sha256=summary_sha256(view),
        executions=tuple(
            (
                value.execution_id,
                identity_sha256(value.settlement) if value.settlement else None,
            )
            for value in view.executions
        ),
        matrix_rows=tuple(row.row_id for row in view.matrix_history),
        feeds={
            state.journal: state.feed.freeze_id for state in view.sampling if state.feed
        },
        sampling_events={
            state.journal: tuple(event.event_id for event in state.history)
            for state in view.sampling
        },
    )


def load_summary(
    connection: Connection,
    view: AbstractAuditView,
    digest: str,
    *,
    register: bool = False,
    captured: SummaryBoundary | None = None,
    reason: FixtureReason = FixtureReason.CORRUPT_REFERENCE,
) -> AbstractAuditView:
    stored = (
        connection.execute(
            select(summaries).where(summaries.c.summary_sha256 == digest)
        )
        .mappings()
        .first()
    )
    if stored is None:
        if captured is None:
            raise FixtureError(reason, path="entries.audit_reference.summary_sha256")
        boundary = captured
    else:
        try:
            boundary = SummaryBoundary.model_validate_json(stored["content_json"])
        except (ValidationError, ValueError, TypeError):
            raise FixtureError(reason, path="audit.summary") from None
        if (
            boundary.plan_id != stored["plan_id"]
            or boundary.model_dump_json() != stored["content_json"]
        ):
            raise FixtureError(reason, path="audit.summary")
    try:
        current = boundary_for(view)
        if (
            boundary.plan_id != view.plan.plan_id
            or boundary.summary_sha256 != digest
            or boundary.feeds != current.feeds
            or boundary.sampling_events != current.sampling_events
            or boundary.matrix_rows != current.matrix_rows[: len(boundary.matrix_rows)]
            or tuple(key for key, _ in boundary.executions)
            != tuple(key for key, _ in current.executions[: len(boundary.executions)])
        ):
            raise ValueError("summary_boundary")
        executions = []
        for value, (_, settlement_hash) in zip(
            view.executions, boundary.executions, strict=False
        ):
            if settlement_hash is not None and (
                value.settlement is None
                or identity_sha256(value.settlement) != settlement_hash
            ):
                raise ValueError("summary_settlement")
            executions.append(
                value
                if settlement_hash is not None
                else value.model_copy(update={"settlement": None})
            )
        candidate = project(
            SamplingAuditView(
                plan=view.plan, executions=tuple(executions), sampling=view.sampling
            ),
            view.matrix_history[: len(boundary.matrix_rows)],
        )
        if candidate.status != "complete" or summary_sha256(candidate) != digest:
            raise ValueError("summary_hash")
        if stored is None and register:
            connection.execute(
                summaries.insert().values(
                    summary_sha256=digest,
                    plan_id=view.plan.plan_id,
                    content_json=boundary.model_dump_json(),
                )
            )
        return candidate
    except (ValidationError, ValueError, TypeError, KeyError):
        raise FixtureError(reason, path="audit.summary") from None


def validate_summaries(
    connection: Connection, views: tuple[AbstractAuditView, ...]
) -> None:
    indexed = {view.plan.plan_id: view for view in views}
    for row in connection.execute(select(summaries)).mappings():
        if row["plan_id"] not in indexed:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="audit.summary")
        load_summary(connection, indexed[row["plan_id"]], row["summary_sha256"])
