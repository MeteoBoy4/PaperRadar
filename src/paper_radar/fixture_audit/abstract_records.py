"""持久化摘要解释的只读链核验与投影。"""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import Connection, select

from paper_radar.fixture_audit.abstract_models import (
    AbstractAuditView,
    MatrixRow,
)
from paper_radar.fixture_audit.abstract_rules import (
    applicable_requests,
    matrix_request_key,
    project,
    retained_acquisition,
    row_key,
)
from paper_radar.fixture_audit.abstract_tables import abstract_rows
from paper_radar.fixture_audit.acquisition_models import (
    identity_sha256,
)
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.resume_rules import (
    can_continue,
)
from paper_radar.fixture_audit.sampling_models import SamplingAuditView


def load_abstracts(
    connection: Connection, views: tuple[SamplingAuditView, ...]
) -> tuple[AbstractAuditView, ...]:
    expected = {
        view.plan.plan_id: {
            row_key(member.member_id, request): (member, request)
            for member, request in applicable_requests(view)
        }
        for view in views
    }
    by_plan = {view.plan.plan_id: view for view in views}
    all_executions = {
        execution.execution_id: execution
        for view in views
        for execution in view.executions
    }
    rows: dict[str, list[MatrixRow]] = {view.plan.plan_id: [] for view in views}
    try:
        latest: dict[tuple[str, tuple[str, str, str, str]], MatrixRow] = {}
        for record in connection.execute(
            select(abstract_rows).order_by(abstract_rows.c.event_no)
        ).mappings():
            row = MatrixRow.model_validate_json(record["content_json"])
            key = row_key(row.member_id, row.request)
            execution = all_executions.get(row.acquisition_id or "")
            if (
                row.plan_id not in expected
                or key not in expected[row.plan_id]
                or expected[row.plan_id][key][1] != row.request
                or row.row_id != record["row_id"]
                or row.interpretation_pending
                or row.generation != record["generation"]
                or row.previous_row_id != record["previous_row_id"]
                or row.plan_id != record["plan_id"]
                or row.member_id != record["member_id"]
                or row.request.route != record["route"]
                or row.request.channel != record["channel"]
                or row.request.acquisition_strategy_version
                != record["strategy_version"]
                or row.acquisition_id != record["acquisition_id"]
                or row.model_dump_json() != record["content_json"]
                or identity_sha256(row.model_copy(update={"row_id": ""})) != row.row_id
                or execution is None
                or execution.plan_id != row.plan_id
                or execution.request != row.request
                or execution.settlement is None
                or row.observed_at != execution.settlement.settled_at
                or row.payload_sha256 != execution.settlement.payload_sha256
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
                )
            if row.reason == "not_attempted" and (
                execution.reason != "not_attempted"
                or execution.physical_requests != 0
                or execution.settlement.artifact_id is not None
                or row.payload_sha256 is not None
                or row.valid_record
                or row.candidates
                or row.excluded_blocks
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
                )
            member, request = expected[row.plan_id][key]
            prior_id = retained_acquisition(by_plan[row.plan_id], member, request)
            previous = latest.get((row.plan_id, key))
            if previous is None:
                if (
                    row.generation != 1
                    or row.previous_row_id is not None
                    or (
                        prior_id is None and execution.previous_execution_id is not None
                    )
                    or (prior_id is not None and execution.execution_id != prior_id)
                    or (
                        prior_id is None
                        and execution.request_key
                        != matrix_request_key(member.member_id, request)
                    )
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="abstract.acquisition"
                    )
            elif (
                row.generation != previous.generation + 1
                or row.previous_row_id != previous.row_id
                or execution.previous_execution_id != previous.acquisition_id
                or not can_continue(all_executions[previous.acquisition_id or ""])
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="abstract.continuation"
                )
            latest[(row.plan_id, key)] = row
            rows[row.plan_id].append(row)
        return tuple(project(view, tuple(rows[view.plan.plan_id])) for view in views)
    except (ValidationError, ValueError, TypeError, KeyError):
        raise FixtureError(
            FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
        ) from None
