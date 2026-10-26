"""摘要矩阵执行和历史解释;外部取得与短事务分开。"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.fixture_audit.abstract_models import (
    AbstractAuditView,
    AbstractCandidate,
    ExcludedBlock,
    MatrixRow,
)
from paper_radar.fixture_audit.abstract_parser import parse_material
from paper_radar.fixture_audit.abstract_rules import (
    applicable_requests,
    matrix_request_key,
    project,
    retained_acquisition,
    row_key,
)
from paper_radar.fixture_audit.abstract_tables import abstract_rows
from paper_radar.fixture_audit.acquisition_models import (
    CodeIdentity,
    RouteExecution,
    SourceRequest,
    identity_sha256,
)
from paper_radar.fixture_audit.acquisition_policy import validate_contact
from paper_radar.fixture_audit.acquisition_records import load_audits
from paper_radar.fixture_audit.acquisition_service import AcquisitionService
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.sampling_models import SamplingAuditView, SamplingMember
from paper_radar.fixture_audit.sampling_records import load_sampling
from paper_radar.fixture_audit.sampling_service import SamplingService
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


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
        for record in connection.execute(select(abstract_rows)).mappings():
            row = MatrixRow.model_validate_json(record["content_json"])
            key = row_key(row.member_id, row.request)
            execution = all_executions.get(row.acquisition_id or "")
            if (
                row.plan_id not in expected
                or key not in expected[row.plan_id]
                or expected[row.plan_id][key][1] != row.request
                or row.row_id != record["row_id"]
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
            member, request = expected[row.plan_id][key]
            prior_id = retained_acquisition(by_plan[row.plan_id], member, request)
            if (prior_id is not None and execution.execution_id != prior_id) or (
                prior_id is None
                and execution.request_key
                != matrix_request_key(member.member_id, request)
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="abstract.acquisition"
                )
            rows[row.plan_id].append(row)
        return tuple(project(view, tuple(rows[view.plan.plan_id])) for view in views)
    except (ValidationError, ValueError, TypeError, KeyError):
        raise FixtureError(
            FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
        ) from None


class AbstractService:
    def __init__(
        self,
        database: Path,
        data_root: Path | None,
        acquisitions: AcquisitionService,
        sampling: SamplingService,
    ) -> None:
        self.database, self.data_root, self.acquisitions, self.sampling = (
            database,
            data_root,
            acquisitions,
            sampling,
        )

    def list_audits(self) -> tuple[AbstractAuditView, ...]:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                return load_abstracts(
                    connection, load_sampling(connection, load_audits(connection))
                )
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
            ) from None
        finally:
            engine.dispose()

    def show_audit(self, plan_id: str) -> AbstractAuditView:
        for view in self.list_audits():
            if view.plan.plan_id == plan_id:
                return view
        raise FixtureError(FixtureReason.RECORD_NOT_FOUND, path="plan_id")

    def _raw(self, execution: RouteExecution) -> bytes:
        if (
            self.data_root is None
            or not execution.settlement
            or not execution.settlement.artifact_id
        ):
            raise FixtureError(
                FixtureReason.EVIDENCE_REQUIRED, path="abstract.material"
            )
        return ArtifactStore(self.database, self.data_root).read_artifact(
            execution.settlement.artifact_id
        )["payload"]

    def _interpret(
        self,
        view: SamplingAuditView,
        member: SamplingMember,
        request: SourceRequest,
        execution: RouteExecution,
    ) -> tuple[MatrixRow, dict[str, str]]:
        settlement = execution.settlement
        assert settlement is not None
        candidates: tuple[AbstractCandidate, ...] = ()
        excluded: tuple[ExcludedBlock, ...] = ()
        texts: dict[str, str] = {}
        reason = settlement.reason
        valid = False
        if settlement.artifact_id is not None:
            state = next(
                state for state in view.sampling if state.journal == member.journal
            )
            event = next(
                event
                for event in state.history
                if event.event_id == member.selection_event_id
            )
            assert event.candidate is not None
            try:
                candidates, excluded, texts, recognized = parse_material(
                    request,
                    self._raw(execution),
                    decoding=settlement.content_decoding or "utf-8",
                    acquisition_id=execution.execution_id,
                    entry_locator=event.candidate.entry_locator
                    if request.route == "feed"
                    else None,
                )
            except (ValueError, TypeError, KeyError, LookupError):
                reason = "invalid_response"
            else:
                valid = True
                if request.route == "publisher" and (
                    not member.doi or settlement.identity_doi != member.doi
                ):
                    candidates, texts = (), {}
                    reason, valid = "identity_mismatch", False
                elif request.route == "publisher" and not recognized:
                    candidates, texts = (), {}
                    reason = "unrecognized_page_shape"
                else:
                    reason = (
                        "acquired"
                        if any(
                            candidate.field == "abstract" for candidate in candidates
                        )
                        else "record_without_abstract"
                    )
        row = MatrixRow(
            row_id="",
            plan_id=view.plan.plan_id,
            member_id=member.member_id,
            request=request,
            acquisition_id=execution.execution_id,
            reason=reason,
            valid_record=valid,
            observed_at=settlement.settled_at,
            payload_sha256=settlement.payload_sha256,
            candidates=candidates,
            excluded_blocks=excluded,
        )
        return row.model_copy(update={"row_id": identity_sha256(row)}), texts

    def _append(self, row: MatrixRow) -> None:
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    abstract_rows.insert().values(
                        row_id=row.row_id,
                        plan_id=row.plan_id,
                        member_id=row.member_id,
                        route=row.request.route,
                        strategy_version=row.request.acquisition_strategy_version,
                        channel=row.request.channel,
                        acquisition_id=row.acquisition_id,
                        content_json=row.model_dump_json(),
                    )
                )
                load_abstracts(
                    connection, load_sampling(connection, load_audits(connection))
                )
                connection.commit()
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
            ) from None
        finally:
            engine.dispose()

    def run(
        self,
        *,
        contact_email: str | None,
        target_count: int = 5,
        plan_key: str | None = None,
        code_identity: CodeIdentity | None = None,
    ) -> AbstractAuditView:
        contact = validate_contact(contact_email)
        plan = self.acquisitions.create_audit_plan(
            contact_email=contact,
            target_count=target_count,
            plan_key=plan_key,
            code_identity=code_identity,
        )
        with self.acquisitions.audit_execution(plan.plan_id) as guard:
            view = self.sampling.advance(
                plan.plan_id,
                contact_email=contact,
                code_identity=code_identity,
                protection=guard,
            )
            for member, request in applicable_requests(view):
                current = self.show_audit(plan.plan_id)
                if any(
                    row.member_id == member.member_id
                    and row.request == request
                    and row.acquisition_id is not None
                    and row.reason != "not_attempted"
                    for row in current.matrix
                ):
                    continue
                prior_id = retained_acquisition(view, member, request)
                execution = next(
                    (
                        value
                        for value in view.executions
                        if value.execution_id == prior_id and value.request == request
                    ),
                    None,
                )
                if execution is None:
                    execution = self.acquisitions.acquire_source(
                        plan.plan_id,
                        request_key=matrix_request_key(member.member_id, request),
                        request=request,
                        contact_email=contact,
                        protection=guard,
                    )
                if execution.settlement is not None:
                    row, _ = self._interpret(view, member, request, execution)
                    self._append(row)
        return self.show_audit(plan.plan_id)

    def read_text(self, plan_id: str, candidate_id: str) -> str:
        view = self.show_audit(plan_id)
        for row in view.matrix:
            if any(
                candidate.candidate_id == candidate_id for candidate in row.candidates
            ):
                member = next(
                    member
                    for state in view.sampling
                    for member in state.members
                    if member.member_id == row.member_id
                )
                execution = next(
                    value
                    for value in view.executions
                    if value.execution_id == row.acquisition_id
                )
                replay, texts = self._interpret(view, member, row.request, execution)
                if replay != row:
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="abstract.interpretation"
                    )
                return texts[candidate_id]
        raise FixtureError(FixtureReason.RECORD_NOT_FOUND, path="candidate_id")

    def validate_all(self) -> None:
        for view in self.list_audits():
            for row in view.matrix:
                if (
                    row.acquisition_id is None
                    or row.reason == "not_attempted"
                    or next(
                        (
                            value
                            for value in view.executions
                            if value.execution_id == row.acquisition_id
                            and value.settlement is None
                        ),
                        None,
                    )
                ):
                    continue
                member = next(
                    member
                    for state in view.sampling
                    for member in state.members
                    if member.member_id == row.member_id
                )
                execution = next(
                    value
                    for value in view.executions
                    if value.execution_id == row.acquisition_id
                )
                replay, _ = self._interpret(view, member, row.request, execution)
                if replay != row:
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="abstract.interpretation"
                    )
